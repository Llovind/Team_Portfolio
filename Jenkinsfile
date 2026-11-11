def runCommand(String command) {
    if (isUnix()) {
        sh command
    } else {
        bat command
    }
}

def configureDockerWorkspace() {
    def workspace = pwd()
    env.DOCKER_WORKSPACE = workspace
    def container = params.JENKINS_CONTAINER == null ? 'jenkins-server' : params.JENKINS_CONTAINER.trim()
    if (!container) {
        return
    }
    if (!isUnix() || !(container ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/)) {
        error('JENKINS_CONTAINER must name the Linux container running this executor; leave blank for a native agent.')
    }
    def home = env.JENKINS_HOME ?: '/var/jenkins_home'
    if (!(home ==~ /\/[A-Za-z0-9_.\/-]+/) || !workspace.startsWith(home + '/')) {
        error('The workspace must be inside the mounted Jenkins home for container mode.')
    }
    // Docker bind sources resolve on the daemon host, not inside the Jenkins container.
    def source = sh(returnStdout: true, script: "docker inspect --format '{{range .Mounts}}{{if eq .Destination \"${home}\"}}{{.Source}}{{end}}{{end}}' ${container}").trim()
    if (!source.startsWith('/') || source.contains('\n')) {
        error('Cannot locate the Jenkins home mount on the Docker host.')
    }
    env.DOCKER_WORKSPACE = source + workspace.substring(home.length())
    echo "Docker workspace: ${env.DOCKER_WORKSPACE}"
}

pipeline {
    agent { label 'team-portfolio' }
    parameters {
        string(name: 'JENKINS_CONTAINER', defaultValue: 'jenkins-server', description: 'Container running this executor. Leave blank for a native host agent.')
    }
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
                script {
                    runCommand('git log -1 --format=fuller')
                    configureDockerWorkspace()
                }
            }
        }
        stage('Syntax Check') {
            steps {
                script {
                    def mount = "type=bind,source=${env.DOCKER_WORKSPACE},target=/workspace,readonly"
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
                    def mount = "type=bind,source=${env.DOCKER_WORKSPACE},target=/workspace"
                    runCommand("docker run --rm --mount \"${mount}\" --workdir /workspace python:3.12-slim python -B tools/prepare_release.py --build-number ${env.BUILD_NUMBER}")
                    env.FRONTEND_SOURCE = "${env.DOCKER_WORKSPACE}/.deployments/build-${env.BUILD_NUMBER}/frontend"
                    env.NGINX_SOURCE = "${env.DOCKER_WORKSPACE}/.deployments/build-${env.BUILD_NUMBER}/nginx/default.conf"
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
