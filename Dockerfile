FROM spleeter:0.3

# 设置环境变量 
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY . /app/

VOLUME [ "/app/static/files", "/app/static/tmp" ]

CMD ["python", "start.py"]