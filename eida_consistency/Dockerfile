#############################################
from ghcr.io/eida/eida-consistency:latest

WORKDIR /app
COPY ../eida_nodes ./eida_nodes
ADD automate_eida_consistency.py .
RUN automate_eida_consistency.py
