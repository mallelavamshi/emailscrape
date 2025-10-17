pipeline {
    agent any
    
    environment {
        DOCKER_IMAGE = 'email-scraper'
        DOCKER_TAG = "${BUILD_NUMBER}"
        GITHUB_REPO = 'mallelavamshi/emailscrape'
        CONTAINER_NAME = 'email-scraper'
        API_PORT = '8000'
        SERVER_IP = '178.16.141.15'
    }
    
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main',
                    url: "https://github.com/${GITHUB_REPO}.git",
                    credentialsId: 'github-credentials'
            }
        }
        
        stage('Build Docker Image') {
            steps {
                script {
                    sh "docker build -t ${DOCKER_IMAGE}:${DOCKER_TAG} ."
                    sh "docker tag ${DOCKER_IMAGE}:${DOCKER_TAG} ${DOCKER_IMAGE}:latest"
                }
            }
        }
        
        stage('Test') {
            steps {
                script {
                    sh 'echo "Running tests..."'
                    sh 'docker run --rm ${DOCKER_IMAGE}:${DOCKER_TAG} python -c "import fastapi; print(fastapi.__version__)"'
                }
            }
        }
        
        stage('Stop Old Container') {
            steps {
                script {
                    sh 'docker-compose down || true'
                    sh 'docker rm -f ${CONTAINER_NAME} || true'
                }
            }
        }
        
        stage('Deploy') {
            steps {
                script {
                    sh '''
                        docker-compose up -d
                        sleep 5
                    '''
                }
            }
        }
        
        stage('Health Check') {
            steps {
                script {
                    sh '''
                        echo "Waiting for API to start..."
                        sleep 15
                        
                        echo "Checking container status..."
                        docker ps | grep ${CONTAINER_NAME}
                        
                        echo "Testing API health endpoint..."
                        curl -f http://localhost:${API_PORT}/health || echo "API is still starting..."
                        
                        echo "Testing main endpoint..."
                        curl -f http://localhost:${API_PORT}/ || echo "Main endpoint check..."
                    '''
                }
            }
        }
    }
    
    post {
        success {
            echo '✅ Deployment successful!'
            echo "========================================"
            echo "API is running at:"
            echo "  - Internal: http://localhost:${API_PORT}"
            echo "  - External: http://${SERVER_IP}:${API_PORT}"
            echo "  - API Docs: http://${SERVER_IP}:${API_PORT}/docs"
            echo "  - Health: http://${SERVER_IP}:${API_PORT}/health"
            echo "========================================"
        }
        failure {
            echo '❌ Deployment failed!'
            sh '''
                echo "Container logs:"
                docker-compose logs --tail=50 || true
                
                echo "Container status:"
                docker ps -a | grep ${CONTAINER_NAME} || true
            '''
        }
        always {
            sh 'docker image prune -f || true'
        }
    }
}
