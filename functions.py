import requests
import cv2
import numpy as np
import urllib.request

from datetime import timezone
from tracer import *
from wxs_db_connection import ApiConnection, ServiceParameters


api = ApiConnection()
serv_parameters = ServiceParameters()
h = {
    'WAccessAuthentication': f'{api.user}:{api.password}',
    'WAccessUtcOffset': '-180'
}


def get_current_datetime():
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S") + f".{now.microsecond // 1000:03d}"


def get_photo_updates_diff(last_biometric_data_update, last_photo_update):
    try:
        if not last_biometric_data_update or not last_photo_update:
            return True

        diff = abs(last_biometric_data_update - last_photo_update).total_seconds()
        if diff < 10:
            return False
        return True

    except Exception as ex:
        report_exception(ex)
        return False


def update_quality(chid, qualidade, photo_cropped, total_faces):
    try:
        reply = requests.get(api.url + f"cardholders/{chid}", headers=h)
        if reply.status_code == 200:
            wxs_user = reply.json()
            wxs_user[serv_parameters.quality] = round(qualidade)
            if photo_cropped:
                wxs_user[serv_parameters.last_photo_update] = get_current_datetime()

            requests.put(api.url + 'cardholders', headers=h, json=wxs_user, params=(("CallAction", False),))

    except Exception as e:
        report_exception(e)


def update_photo(chid, img):
    try:
        reply = requests.put(api.url + f'cardholders/{chid}/photos/1', files=(('photoJpegData', img), ), headers=h)
        if reply.status_code in [requests.codes.ok, requests.codes.no_content]:
            trace(f"Cardholder {chid=}: photo 1 update OK")
        else:
            error("Error: " + str(reply))

    except Exception as ex:
        report_exception(ex)


def baixar_classificador():
    """
    Baixa o classificador Haar Cascade se ele não existir
    """
    diretorio = 'haarcascades'
    arquivo = 'haarcascade_frontalface_default.xml'
    caminho_completo = os.path.join(diretorio, arquivo)

    # Cria o diretório se não existir
    if not os.path.exists(diretorio):
        os.makedirs(diretorio)

    # Baixa o arquivo se não existir
    if not os.path.exists(caminho_completo):
        print("Baixando classificador facial...")
        url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
        urllib.request.urlretrieve(url, caminho_completo)
        print("Classificador baixado com sucesso!")

    return caminho_completo


def calcular_qualidade_rosto(caminho_imagem):
    # Carregar a imagem
    imagem = cv2.imread(caminho_imagem)
    if imagem is None:
        raise Exception("Não foi possível carregar a imagem")

    # Carregar o classificador cascata
    caminho_classificador = baixar_classificador()
    face_cascade = cv2.CascadeClassifier(caminho_classificador)

    if face_cascade.empty():
        raise Exception("Erro ao carregar o classificador facial")

    # Converter para escala de cinza
    gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)

    # Detectar rostos
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30)
    )

    if len(faces) == 0:
        return 0, imagem, 0

    count_faces = len(faces)

    # Pegar o maior rosto detectado (assumindo que é o principal)
    face = max(faces, key=lambda x: x[2] * x[3])
    x, y, width, height = face

    # # Extrair região do rosto
    rosto = imagem[y:y + height, x:x + width]

    # # Dimensões do rosto
    # height, width = rosto.shape[:2]

    # 1. Tamanho do rosto em relação à imagem (0-35 pontos)
    area_rosto = width * height
    area_total = imagem.shape[0] * imagem.shape[1]
    proporcao_area = area_rosto / area_total

    # Valorizando áreas entre 30% e 50% da imagem como ideal
    if proporcao_area < 0.30:
        # Penalização para rostos pequenos
        pontos_tamanho = proporcao_area * 100
    elif proporcao_area > 0.50:
        # Penalização para rostos grandes
        pontos_tamanho = max(0, 35 - (proporcao_area - 0.50) * 150)
    else:
        # Atribui pontos altos para rostos bem enquadrados (entre 30% e 50%)
        pontos_tamanho = min(35, 25 + (proporcao_area - 0.30) * 50)

    # Garantindo que a pontuação esteja dentro da faixa permitida
    pontos_tamanho = min(35, max(0, pontos_tamanho))

    # 2. Análise de nitidez (0-35 pontos)
    gray_rosto = cv2.cvtColor(rosto, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray_rosto, cv2.CV_64F).var()
    # Aplicar uma função logarítmica para controlar o impacto
    pontos_nitidez = min(35, np.log1p(laplacian_var) * 10)

    # 3. Iluminação (0-30 pontos)
    luminancia = cv2.cvtColor(rosto, cv2.COLOR_BGR2LAB)[:, :, 0]
    luminancia_media = np.mean(luminancia)
    # Usando uma penalidade quadrática em torno de 128
    pontos_iluminacao = max(0, 30 - ((128 - luminancia_media) ** 2) / 50)

    # Calcular pontuação final
    pontuacao_final = min(100, pontos_tamanho + pontos_nitidez + pontos_iluminacao)

    return pontuacao_final, imagem, count_faces


def processar_foto(caminho_imagem, chid, margem_percentual=0.40):
    # Carregar a imagem original
    imagem = cv2.imread(caminho_imagem)
    if imagem is None:
        raise ValueError(
            "A imagem não foi carregada. Verifique o caminho fornecido.")

    # Carregar o classificador cascata
    caminho_classificador = baixar_classificador()
    face_cascade = cv2.CascadeClassifier(caminho_classificador)

    if face_cascade.empty():
        raise Exception("Erro ao carregar o classificador facial")

    # Converter a imagem para escala de cinza
    imagem_cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)

    # # Carregar o classificador Haar para detecção de rosto
    # classificador_rosto = cv2.CascadeClassifier(
    #     cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    # Detectar rostos
    rostos = face_cascade.detectMultiScale(
        imagem_cinza, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    # Verificar se algum rosto foi encontrado
    if len(rostos) == 0:
        print("Nenhum rosto encontrado. A imagem original será mantida.")
        return

    # Encontrar o maior rosto
    x, y, w, h = max(rostos, key=lambda r: r[2] * r[3])

    # Calcular a margem para incluir uma área maior ao redor do rosto
    margem_x = int(w * margem_percentual * 0.5)
    margem_y = int(h * margem_percentual)

    # Definir as coordenadas da face com margem, garantindo que estejam dentro da imagem
    x_inicio = max(x - margem_x, 0)
    y_inicio = max(y - margem_y, 0)
    x_fim = min(x + w + margem_x, imagem.shape[1])
    y_fim = min(y + h + margem_y, imagem.shape[0])

    # Extrair a região da face com a margem
    face_cortada = imagem[y_inicio:y_fim, x_inicio:x_fim]

    # # Definir os caminhos de salvamento
    # caminho_original_backup = os.path.splitext(
    #     caminho_imagem)[0] + "_original.jpg"
    # caminho_face = caminho_imagem  # Salvando a face no lugar da imagem original

    # # Definir os caminhos de salvamento
    # caminho_face = os.path.splitext(
    #     caminho_imagem)[0] + "_original.jpg"
    # caminho_original_backup = caminho_imagem

    # Salvar a imagem original em um novo caminho
    photo_2_path = f"C:\\Program Files (x86)\\Invenzi\\Invenzi W-Access\\Web Application\\PhotoID\\Photo_2\\{chid}_2.jpg"
    cv2.imwrite(photo_2_path, imagem)
    print(f"A imagem original foi salva em: {photo_2_path}")

    return cv2.imencode('.jpg', face_cortada)
    # # Salvar a imagem da face cortada (com margem) no caminho original
    # cv2.imwrite(caminho_face, face_cortada)
    # print(f"A imagem da face foi salva em: {caminho_face}")
