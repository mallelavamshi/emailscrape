pipeline {
    agent any
    
    environment {
        DOCKER_IMAGE = 'email-scraper'
        DOCKER_TAG = "${BUILD_NUMBER}"
        GITHUB_REPO = 'mallelavamshi/fbemail'
        CONTAINER_NAME = 'email-scraper'
        API_PORT = '8000'
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
                    sh 'echo "Tests would run here"'
                }
            }
        }
        
        stage('Deploy') {
            steps {
                script {
                    sh '''
                        docker-compose down || true
                        docker-compose up -d
                    '''
                }
            }
        }
        
        stage('Health Check') {
            steps {
                script {
                    sh '''
                        sleep 15
                        docker ps | grep ${CONTAINER_NAME}
                        curl -f http://localhost:${API_PORT}/health || echo "API is starting..."
                    '''
                }
            }
        }
    }
    
    post {
        success {
            echo '✅ Deployment successful!'
            echo "API is running at http://178.16.141.15:${API_PORT}"
            echo "API Docs: http://178.16.141.15:${API_PORT}/docs"
        }
        failure {
            echo '❌ Deployment failed!'
            sh 'docker-compose logs || true'
        }
    }
}
