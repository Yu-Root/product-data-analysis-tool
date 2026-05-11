FROM docker.m.daocloud.io/python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY product-data-analysis-tool/ ./

RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

RUN playwright install --with-deps chromium

EXPOSE 5000

CMD ["python", "main.py"]
