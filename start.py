import logging
import threading
from flask import Flask, request, render_template, jsonify, send_from_directory
import os
from gevent.pywsgi import WSGIServer, WSGIHandler
from logging.handlers import RotatingFileHandler

import vocal
from vocal import cfg, tool
from vocal.cfg import ROOT_DIR
import subprocess
from spleeter.separator import Separator
from flask import send_file
import shutil

class CustomRequestHandler(WSGIHandler):
    def log_request(self):
        pass

# 禁用 Werkzeug 默认的日志处理器
log = logging.getLogger('werkzeug')
log.handlers[:] = []
log.setLevel(logging.WARNING)

app = Flask(__name__, static_folder=os.path.join(ROOT_DIR, 'static'), static_url_path='/static',
            template_folder=os.path.join(ROOT_DIR, 'templates'))
root_log = logging.getLogger()  # Flask的根日志记录器
root_log.handlers = []
root_log.setLevel(logging.WARNING)

# 配置日志
app.logger.setLevel(logging.WARNING)  # 设置日志级别为 INFO
# 创建 RotatingFileHandler 对象，设置写入的文件路径和大小限制
file_handler = RotatingFileHandler(os.path.join(ROOT_DIR, 'vocal.log'), maxBytes=1024 * 1024, backupCount=5)
# 创建日志的格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# 设置文件处理器的级别和格式
file_handler.setLevel(logging.WARNING)
file_handler.setFormatter(formatter)
# 将文件处理器添加到日志记录器中
app.logger.addHandler(file_handler)


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.config['STATIC_FOLDER'], filename)

@app.route('/')
def index():
    return render_template("index.html",version=vocal.version_str,cuda=cfg.cuda, language=cfg.LANG,root_dir=ROOT_DIR.replace('\\', '/'))


# 上传音频
@app.route('/upload', methods=['POST'])
def upload():
    try:
        # 获取上传的文件
        audio_file = request.files['audio']
        # 如果是mp4
        noextname, ext = os.path.splitext(audio_file.filename)
        ext = ext.lower()
        # 如果是视频，先分离
        wav_file = os.path.join(cfg.TMP_DIR, f'{noextname}.wav')
        if os.path.exists(wav_file) and os.path.getsize(wav_file) > 0:
            return jsonify({'code': 0, 'msg': cfg.transobj['lang1'], "data": os.path.basename(wav_file)})
        msg=""
        if ext in ['.mp4', '.mov', '.avi', '.mkv', '.mpeg', '.mp3', '.flac']:
            video_file = os.path.join(cfg.TMP_DIR, f'{noextname}{ext}')
            audio_file.save(video_file)
            params = [
                "-i",
                video_file,
            ]
            if ext not in ['.mp3', '.flac']:
                params.append('-vn')
            params.append(wav_file)
            rs = tool.runffmpeg(params)
            if rs != 'ok':
                return jsonify({"code": 1, "msg": rs})
            msg=","+cfg.transobj['lang9']
        elif ext == '.wav':
            audio_file.save(wav_file)
        else:
            return jsonify({"code": 1, "msg": f"{cfg.transobj['lang3']} {ext}"})

        # 返回成功的响应
        return jsonify({'code': 0, 'msg': cfg.transobj['lang1']+msg, "data": os.path.basename(wav_file)})
    except Exception as e:
        app.logger.error(f'[upload]error: {e}')
        return jsonify({'code': 2, 'msg': cfg.transobj['lang2']})


# 根据文本返回tts结果，返回 name=文件名字，filename=文件绝对路径
# 请求端根据需要自行选择使用哪个
# params
# wav_name:tmp下的wav文件
# model 模型名称
@app.route('/process', methods=['GET', 'POST'])
def process():
    # 原始字符串
    wav_name = request.form.get("wav_name").strip()
    model = request.form.get("model")
    wav_file = os.path.join(cfg.TMP_DIR, wav_name)
    noextname = wav_name[:-4]
    if not os.path.exists(wav_file):
        return jsonify({"code": 1, "msg": f"{wav_file} {cfg.langlist['lang5']}"})
    if not os.path.exists(os.path.join(cfg.MODEL_DIR, model, 'model.meta')):
        return jsonify({"code": 1, "msg": f"{model} {cfg.transobj['lang4']}"})
    try:
        p=subprocess.run(['ffprobe','-v','error','-show_entries',"format=duration",'-of', "default=noprint_wrappers=1:nokey=1", wav_file], capture_output=True)      
        if p.returncode==0:
            sec=float(p.stdout)  
    except:
        sec=1800
    print(f'{sec=}')
    separator = Separator(f'spleeter:{model}', multiprocess=False)
    dirname = os.path.join(cfg.FILES_DIR, noextname)
    try:
        separator.separate_to_file(wav_file, destination=dirname, filename_format="{instrument}.{codec}", duration=sec)
    except Exception as e:
        return jsonify({"code": 1, "msg": str(e)})
    status={
        "accompaniment":"伴奏",
        "bass":"低音",
        "drums":"鼓",
        "piano":"琴",
        "vocals":"人声",
        "other":"其他"
    }
    data = []
    urllist = []
    for it in os.listdir(dirname):
        if it.endswith('.wav'):
            data.append( status[it[:-4]] if cfg.LANG=='zh' else it[:-4])
            urllist.append(f'http://{cfg.web_address}/static/files/{noextname}/{it}')

    return jsonify({"code": 0, "msg": cfg.transobj['lang6'], "data": data, "urllist": urllist,"dirname":dirname})


@app.route('/api',methods=['POST'])
def api():
    try:
        # 获取上传的文件
        audio_file = request.files['file']
        model = request.form.get("model")
        # 如果是mp4
        noextname, ext = os.path.splitext(audio_file.filename)
        ext = ext.lower()
        # 如果是视频，先分离
        wav_file = os.path.join(cfg.TMP_DIR, f'{noextname}.wav')
        if not os.path.exists(wav_file) or os.path.getsize(wav_file) == 0:
            if ext in ['.mp4', '.mov', '.avi', '.mkv', '.mpeg', '.mp3', '.flac']:
                video_file = os.path.join(cfg.TMP_DIR, f'{noextname}{ext}')
                audio_file.save(video_file)
                params = [
                    "-i",
                    video_file,
                ]
                if ext not in ['.mp3', '.flac']:
                    params.append('-vn')
                params.append(wav_file)
                rs = tool.runffmpeg(params)
                if rs != 'ok':
                    return jsonify({"code": 1, "msg": rs})
            elif ext == '.wav':
                audio_file.save(wav_file)
            else:
                return jsonify({"code": 1, "msg": f"{cfg.transobj['lang3']} {ext}"})

        # 返回成功的响应
        if not os.path.exists(wav_file):
            return jsonify({"code": 1, "msg": f"{wav_file} {cfg.langlist['lang5']}"})
        if not os.path.exists(os.path.join(cfg.MODEL_DIR, model, 'model.meta')):
            return jsonify({"code": 1, "msg": f"{model} {cfg.transobj['lang4']}"})
        try:
            p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', "format=duration", '-of',
                                "default=noprint_wrappers=1:nokey=1", wav_file], capture_output=True)
            if p.returncode == 0:
                sec = float(p.stdout)
        except:
            sec = 1800
        print(f'{sec=}')
        separator = Separator(f'spleeter:{model}', multiprocess=False)
        dirname = os.path.join(cfg.FILES_DIR, noextname)
        try:
            separator.separate_to_file(wav_file, destination=dirname, filename_format="{instrument}.{codec}",
                                       duration=sec)
        except Exception as e:
            return jsonify({"code": 1, "msg": str(e)})
        status = {
            "accompaniment.wav":"accompaniment audio" if cfg.LANG=='en' else "伴奏",
            "bass.wav": "bass audio" if cfg.LANG=='en' else"低音",
            "drums.wav": "drums audio" if cfg.LANG=='en' else"鼓",
            "piano.wav": "piano audio" if cfg.LANG=='en' else"琴",
            "vocals.wav": "vocals audio" if cfg.LANG=='en' else"人声",
            "other.wav": "other audio" if cfg.LANG=='en' else"其他"
        }
        # data = []
        urllist = []
        for it in os.listdir(dirname):
            if it.endswith('.wav'):
                urllist.append(f'http://{cfg.web_address}/static/files/{noextname}/{it}')

        return jsonify({"code": 0, "msg": cfg.transobj['lang6'], "data": urllist,"status_text":status})
    except Exception as e:
        app.logger.error(f'[upload]error: {e}')
        return jsonify({'code': 2, 'msg': cfg.transobj['lang2']})



@app.route('/checkupdate', methods=['GET', 'POST'])
def checkupdate():
    return jsonify({'code': 0, "msg": cfg.updatetips})


@app.route('/api/vocals', methods=['POST'])
def api_vocals():
    """
    接收音频文件，分离人声，返回vocals.wav，成功后删除缓存和输出目录。
    """
    try:
        audio_file = request.files.get('file')
        if not audio_file:
            return jsonify({"code": 1, "msg": "未提供音频文件"}), 400

        noextname, ext = os.path.splitext(audio_file.filename)
        ext = ext.lower()
        wav_file = os.path.join(cfg.TMP_DIR, f'{noextname}.wav')

        # 先转为wav
        if not os.path.exists(wav_file) or os.path.getsize(wav_file) == 0:
            if ext in ['.mp4', '.mov', '.avi', '.mkv', '.mpeg', '.mp3', '.flac']:
                video_file = os.path.join(cfg.TMP_DIR, f'{noextname}{ext}')
                audio_file.save(video_file)
                params = ["-i", video_file]
                if ext not in ['.mp3', '.flac']:
                    params.append('-vn')
                params.append(wav_file)
                rs = tool.runffmpeg(params)
                if rs != 'ok':
                    return jsonify({"code": 1, "msg": rs}), 400
            elif ext == '.wav':
                audio_file.save(wav_file)
            else:
                return jsonify({"code": 1, "msg": f"不支持的文件格式 {ext}"}), 400

        # 检查模型
        model = '2stems'
        if not os.path.exists(os.path.join(cfg.MODEL_DIR, model, 'model.meta')):
            return jsonify({"code": 1, "msg": f"模型 {model} 不存在"}), 400

        # 获取音频时长
        try:
            p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', "format=duration", '-of',
                                "default=noprint_wrappers=1:nokey=1", wav_file], capture_output=True)
            if p.returncode == 0:
                sec = float(p.stdout)
            else:
                sec = 1800
        except Exception:
            sec = 1800

        # 分离
        separator = Separator(f'spleeter:{model}', multiprocess=False)
        dirname = os.path.join(cfg.FILES_DIR, noextname)
        try:
            separator.separate_to_file(wav_file, destination=dirname, filename_format="{instrument}.{codec}", duration=sec)
        except Exception as e:
            return jsonify({"code": 1, "msg": str(e)}), 500

        # 查找vocals.wav
        vocals_path = os.path.join(dirname, 'vocals.wav')
        if not os.path.exists(vocals_path):
            # 清理缓存
            try:
                if os.path.exists(wav_file):
                    os.remove(wav_file)
                if os.path.exists(dirname):
                    shutil.rmtree(dirname)
            except Exception:
                pass
            return jsonify({"code": 1, "msg": "未找到分离后的人声文件"}), 500

        # 直接返回文件流
        response = send_file(vocals_path, as_attachment=True, download_name='vocals.wav')

        # 清理缓存和输出
        try:
            if os.path.exists(wav_file):
                os.remove(wav_file)
            if os.path.exists(dirname):
                shutil.rmtree(dirname)
            # 删除上传的原始视频/音频
            video_file = os.path.join(cfg.TMP_DIR, f'{noextname}{ext}')
            if os.path.exists(video_file):
                os.remove(video_file)
        except Exception:
            pass

        return response
    except Exception as e:
        app.logger.error(f'[api_vocals]error: {e}')
        return jsonify({'code': 2, 'msg': '处理失败'}), 500

if __name__ == '__main__':
    http_server = None
    try:
        threading.Thread(target=tool.checkupdate).start()        
        try:
            host = cfg.web_address.split(':')
            http_server = WSGIServer((host[0], int(host[1])), app ,handler_class=CustomRequestHandler)
            threading.Thread(target=tool.openweb, args=(cfg.web_address,)).start()
            http_server.serve_forever()
        finally:
            if http_server:
                http_server.stop()
    except Exception as e:
        if http_server:
            http_server.stop()
        print("error:" + str(e))
        app.logger.error(f"[app]start error:{str(e)}")
