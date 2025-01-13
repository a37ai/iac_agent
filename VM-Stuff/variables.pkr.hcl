# variables.pkr.hcl
#
# Holds commonly adjusted parameters for the Windows DevOps base image.

# ----------------------------------------------------------------------------
# Basic Parameters
# ----------------------------------------------------------------------------
variable "ami_name_prefix" {
  type    = string
  default = "win-devops-base"
}

variable "environment_tag" {
  type    = string
  default = "Build"
}

variable "temp_path" {
  type    = string
  default = "C:/Temp"
}

variable "winrm_username" {
  type    = string
  default = "Administrator"
}

# ----------------------------------------------------------------------------
# AWS Settings
# ----------------------------------------------------------------------------
variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "source_ami" {
  # 2025 Windows AMI
  type    = string
  default = "ami-09ec59ede75ed2db7"
}

variable "instance_type" {
  type    = string
  default = "t3.large"
}

# ----------------------------------------------------------------------------
# Tool Versions (Pinnable)
# ----------------------------------------------------------------------------
variable "terraform_version" {
  type    = string
  default = "1.5.5"
}

variable "helm_version" {
  type    = string
  default = "v3.12.3"
}

variable "chef_workstation_version" {
  type    = string
  default = "23.6.1031"
}

variable "puppet_agent_version" {
  type    = string
  default = "latest"
}

variable "jenkins_version" {
  type    = string
  default = "2.401.3"
}

variable "python_version" {
  type    = string
  default = "3.11.5"
}

variable "aws_cli_version" {
  type    = string
  default = "2.11.26"
}

variable "prometheus_version" {
  type    = string
  default = "2.45.0"
}

variable "vault_version" {
  type    = string
  default = "1.14.2"
}
