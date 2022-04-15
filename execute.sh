#!/bin/bash
ssh cyp25@caelum-102.cl.cam.ac.uk << EOF
    cd K8s-Consensus/server
    kubectl delete deployments/client
    python3 -u server.py
EOF
