FROM python:3.13-slim
WORKDIR /research
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
COPY src ./src
COPY dashboard ./dashboard
COPY configs ./configs
COPY tests ./tests
RUN pip install --no-deps -e .
ENV PYTHONUNBUFFERED=1
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
