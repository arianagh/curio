variable "REGISTRY" {
  default = "ghcr.io/arianagh/curio"
}

// Overridden by the CI job's TAG env var (github.sha); defaults to "dev" for
// local `docker buildx bake` runs.
variable "TAG" {
  default = "dev"
}

group "default" {
  targets = ["worker"]
}

target "worker" {
  context    = "."
  dockerfile = "Dockerfile"
  tags = [
    "${REGISTRY}:latest",
    "${REGISTRY}:${TAG}",
  ]
  cache-from = ["type=gha"]
  cache-to   = ["type=gha,mode=max"]
}
