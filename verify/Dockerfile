FROM python:3.12-slim

WORKDIR /verify

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY test_acceptance.py .

ENV API_BASE=http://api:8000
ENV WEB_BASE=http://web:80

# 一次性验收：跑完即退出，退出码即验收结果
CMD ["pytest", "-v", "--tb=short", "-p", "no:cacheprovider"]
