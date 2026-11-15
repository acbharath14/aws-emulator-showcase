variable "prefix" {
  description = "Name prefix for every resource. Distinct from the pytest suite's per-test prefixes, so the two never collide."
  type        = string
  default     = "tf"
}

variable "region" {
  description = "Region sent with every call. The emulator accepts any region; us-east-1 matches the Python side."
  type        = string
  default     = "us-east-1"
}

variable "emulator_endpoint" {
  description = "HTTPS endpoint of the local emulator. Every service is served on this one endpoint."
  type        = string
  default     = "https://127.0.0.1:9297"
}

variable "emulator_port" {
  description = "Port the emulator serves on. Used to locate the per-run credentials file and CA bundle under ~/.aws/emulator/<port>/."
  type        = number
  default     = 9297
}
