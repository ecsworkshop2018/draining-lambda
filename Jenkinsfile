pipeline {
    agent none

    environment {
        LAMBDA_SRC_DIR = "function"
    }

    stages {
        stage("lambda-unit-test") {
            agent { label 'master' }
            steps {
                dir("${LAMBDA_SRC_DIR}") {
                    sh """
                        rm -rf .pytest_cache
                        rm -rf venv
                        virtualenv venv
                        source venv/bin/activate
                        pip install -r requirement.txt
                        pytest -vv
                        deactivate
                        rm -rf venv
                    """
                }
            }
        }
    }
}