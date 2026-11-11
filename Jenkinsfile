def runCommand(String command) {
    if (isUnix()) {
        sh command
    } else {
        bat command
    }
}

pipeline {
    agent { label 'team-portfolio' }
    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '15'))
    }
    triggers {
        githubPush()
    }
    environment {
        FRONTEND_PORT = '8082'
    }
    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script { runCommand('git log -1 --format=fuller') }
            }
        }
        stage('Syntax Check') {
            steps {
                script {
                    // The agent and Docker daemon must share this workspace path.
                    def mount = "type=bind,source=${pwd()},target=/workspace,readonly"
                    runCommand('docker info')
                    runCommand('docker compose config --quiet')
                    runCommand("docker run --rm --mount \"${mount}\" --workdir /workspace python:3.12-slim python -B -m unittest discover -s tests -v")
                    runCommand("docker run --rm --mount \"${mount}\" --workdir /workspace node:22-alpine node --check frontend/js/api.js")
                    runCommand("docker run --rm --mount \"${mount}\" --workdir /workspace node:22-alpine node --check frontend/js/dashboard.js")
                    runCommand("docker run --rm --mount \"${mount}\" --workdir /workspace node:22-alpine node --check frontend/js/profile.js")
                    runCommand("docker run --rm --mount \"${mount}\" --workdir /workspace node:22-alpine node --check frontend/js/github.js")
                    runCommand("docker run --rm --mount \"${mount}\" --workdir /workspace node:22-alpine node --test tests/frontend.test.cjs tests/github_frontend.test.cjs")
                }
            }
        }
        stage('Build Image') {
            steps {
                script {
                    runCommand('docker compose build --pull backend')
                    runCommand('docker compose pull frontend')
                }
            }
        }
        stage('Automated Deployment') {
            steps {
                script {
                    def mount = "type=bind,source=${pwd()},target=/workspace"
                    runCommand("docker run --rm --mount \"${mount}\" --workdir /workspace python:3.12-slim python -B tools/prepare_release.py --build-number ${env.BUILD_NUMBER}")
                    runCommand("docker compose -f .deployments/build-${env.BUILD_NUMBER}/docker-compose.yml up -d --force-recreate --wait --wait-timeout 120")
                }
            }
        }
        stage('Health Check') {
            steps {
                script {
                    runCommand("docker compose -f .deployments/build-${env.BUILD_NUMBER}/docker-compose.yml exec -T backend python - < tools/check_deployment.py")
                    runCommand("docker compose -f .deployments/build-${env.BUILD_NUMBER}/docker-compose.yml ps")
                }
            }
        }
    }
    post {
        failure {
            script {
                if (fileExists('docker-compose.yml')) {
                    if (isUnix()) {
                        sh returnStatus: true, script: 'docker compose ps; docker compose logs --no-color --tail=80'
                    } else {
                        bat returnStatus: true, script: 'docker compose ps\r\ndocker compose logs --no-color --tail=80'
                    }
                }
            }
        }
    }
}
