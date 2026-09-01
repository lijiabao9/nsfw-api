from flask import Flask, request, Response, jsonify
import json
import urllib.request
import urllib.error
import caffe
import contextlib
import numpy as np
import classify_nsfw
import os
from datetime import datetime

app = Flask(__name__)

# 从环境变量读取 API_KEY，若未设置则使用默认密钥（仅开发用）
API_KEY = os.environ.get("API_KEY", "default_api_key_please_change")
# 只有明确配置为 "false"（不区分大小写）才关闭鉴权，其余情况均开启
AUTH_ENABLE = os.environ.get("AUTH_ENABLE", "True").strip().lower() != "false"

def make_transformer(nsfw_net):
    transformer = caffe.io.Transformer({'data': nsfw_net.blobs['data'].data.shape})
    transformer.set_transpose('data', (2, 0, 1))
    transformer.set_mean('data', np.array([104, 117, 123]))
    transformer.set_raw_scale('data', 255)
    transformer.set_channel_swap('data', (2, 1, 0))
    return transformer

nsfw_net = caffe.Net(
    "/opt/open_nsfw/nsfw_model/deploy.prototxt",
    "/opt/open_nsfw/nsfw_model/resnet_50_1by2_nsfw.caffemodel",
    caffe.TEST
)
caffe_transformer = make_transformer(nsfw_net)

# ---------- 鉴权装饰器 ----------
def require_auth():
    """检查请求中的 key 参数是否匹配 API_KEY"""
    if not AUTH_ENABLE:
        return True  # 鉴权关闭，直接通过
    key = request.args.get('key')
    if not key or key != API_KEY:
        return False
    return True

# ---------- 路由 ----------
@app.route('/health', methods=['GET'])
def health():
    """健康检查接口，无需鉴权"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"status": "UP", "time": now})

@app.route('/batch-classify', methods=['POST'])
def batch_classify():
    if not require_auth():
        return jsonify({"error": "Invalid API key"}), 401

    req_json = request.get_json(force=True)
    if "urls" in req_json:
        image_entries = list(map(lambda u: {'url': u}, req_json["urls"]))
    elif "images" in req_json:
        image_entries = req_json["images"]
    else:
        return 'Accepted formats are {"urls": ["url1", "url2"]} or {"images": [{"url":"url1"}, {"url":"url2"}]}'

    def stream_predictions():
        predictions = classify_from_urls(image_entries).__iter__()
        try:
            prev_prediction = next(predictions)
        except StopIteration:
            yield '{"predictions": []}'
            raise StopIteration
        yield '{"predictions": [\n'
        for prediction in predictions:
            yield json.dumps(prev_prediction) + ',\n'
            prev_prediction = prediction
        yield json.dumps(prev_prediction) + '\n]}'

    return Response(stream_predictions(), mimetype='application/json')

@app.route('/')
def single_classify():
    if not require_auth():
        return jsonify({"error": "Invalid API key"}), 401

    if 'url' in request.args:
        single_image = {'url': request.args.get('url')}
        result = classify_from_urls([single_image]).__next__()
        return jsonify(result)
    else:
        return "Missing url parameter", 400

# ---------- 辅助函数 ----------
def classify_from_urls(image_entries):
    for e in image_entries:
        yield classify_from_url(e, nsfw_net)

def classify_from_url(image_entry, nsfw_net):
    headers = {'User-agent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; de; rv:1.9.1.5) Gecko/20091102 Firefox/3.5.5'}
    try:
        req = urllib.request.Request(image_entry["url"], None, headers)
        with contextlib.closing(urllib.request.urlopen(req)) as stream:
            score = classify(stream.read(), nsfw_net)
            result = {'score': score}
    except urllib.error.HTTPError as e:
        result = {'error_code': e.code, 'error_reason': e.reason}
    except urllib.error.URLError as e:
        result = {'error_code': 500, 'error_reason': str(e.reason)}
    except Exception as e:
        result = {'error_code': 500, 'error_reason': str(e)}
    result.update(image_entry)
    return result

def classify(image_data, nsfw_net):
    scores = classify_nsfw.caffe_preprocess_and_compute(
        image_data,
        caffe_transformer=caffe_transformer,
        caffe_net=nsfw_net,
        output_layers=['prob']
    )
    return scores[1]

if __name__ == '__main__':
    app.run(host='0.0.0.0')