import os

# from photo_quality import calcular_qualidade_rosto, processar_foto
from functions import *
from wxs_db_connection import DatabaseReader, ServiceParameters

sql = DatabaseReader()
serv_parameters = ServiceParameters()

photos_default_path = "C:\\Program Files (x86)\\Invenzi\\Invenzi W-Access\\Web Application\\PhotoID\\Photo_1"


try:
    script = """
SELECT
    bm.CHID,
    Firstname,
    bm.LastUpdate,
    Data,
    AuxDte05 AS 'Last photo update'
FROM CHBiometricData bm
JOIN CHMain m ON m.CHID = bm.CHID
JOIN CHAux a ON  a.CHID = m.CHID
WHERE LastUpdate > DATEADD(day, -1, GETUTCDATE())
"""
    if not (ret := sql.read_data(script)):
        print('Nenhuma foto recente')

    for chid, first_name, last_biometric_data_update, data, last_photo_update in ret:
        try:
            trace(f'{chid= }, {first_name=  }, {last_biometric_data_update= }')
            photo_path = os.path.join(photos_default_path, f"{chid}_1.jpg")
            # print(photo_path)
            qualidade, imagem_resultado, total_faces = calcular_qualidade_rosto(photo_path)
            trace(f"Pontuação de qualidade do rosto: {qualidade:.1f}%")
            if qualidade < 30:
                trace("Imagem com qualidade baixa.")
            else:
                photo_cropped = False
                update_main_photo = get_photo_updates_diff(last_biometric_data_update, last_photo_update)
                if (
                    serv_parameters.cropp_photo
                    and update_main_photo
                ):
                    # Se a foto ainda não foi processada ou se o tempo entre a última atualização do biometria e a última atualização
                    convert_success, new_img = processar_foto(photo_path, chid)
                    if convert_success:
                        update_photo(chid, new_img.tobytes())
                        photo_cropped = True
                    else:
                        trace("Falha ao extrair face da imagem")

            update_quality(chid, qualidade, photo_cropped, total_faces)

        except Exception as ex:
            print('Errro:  ', ex)

except Exception as ex:
    print(f'** Error: {ex}')
