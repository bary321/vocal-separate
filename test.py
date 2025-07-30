# cli 示例
# from spleeter.separator import Separator
# import os
# separator = Separator('spleeter:2stems', multiprocess=False)
# noextname="1"
# dirname=os.path.join("./static/files",noextname)

# separator.separate_to_file("./lao59.mp3", destination=dirname, filename_format="{instrument}.{codec}")
# a_name = f"{dirname}/{noextname}vocals.wav"

# api 请求示例

import requests
# 请求地址
url = "http://172.31.0.7:9999/api"
files = {"file": open("/root/src/baohuo_server/sucai/output/访谈_刘芳毅_audio.wav", "rb")}
data={"model":"2stems"}
response = requests.request("POST", url, timeout=600, data=data,files=files)
print(response.json())