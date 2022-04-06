#!/bin/bash
ssh cyp25@caelum-102.cl.cam.ac.uk << EOF
    cd docker_compose_1/server
    kubectl delete deployments/client
    python3 -u server.py

EOF
