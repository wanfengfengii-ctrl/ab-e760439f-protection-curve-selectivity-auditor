FROM python:3.12-slim
WORKDIR /verify
COPY verify.py ./
# 验收脚本仅用标准库；服务就绪后运行一次即退出。
CMD ["python", "/verify/verify.py"]
