# 使用 openEuler 预构建 Caffe 镜像（支持 amd64, arm64）
FROM openeuler/caffe:1.0-oe2403sp4

# 安装 Python3 及相关工具
RUN dnf update -y && \
    dnf install -y python3 python3-pip python3-devel && \
    dnf clean all

# 设置 Python 软链接
RUN ln -s /usr/bin/python3 /usr/bin/python || true

# 安装 Python 依赖
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# 复制本地 open_nsfw 目录（含 classify_nsfw.py 和模型）
COPY ./open_nsfw /opt/open_nsfw
# 设置 PYTHONPATH
ENV PYTHONPATH=/opt/open_nsfw:$PYTHONPATH

# 复制应用代码
COPY ./web /opt/web
# 设置工作目录
WORKDIR /opt/web

# ---- 修复 Caffe 的 as_grey 参数问题 ----
RUN sed -i 's/as_grey/as_gray/g' /opt/caffe/python/caffe/io.py

# 启动服务
CMD ["sh", "-c", "gunicorn --timeout 360 --bind 0.0.0.0:5000 -k gevent --worker-connections 32 app:app"]