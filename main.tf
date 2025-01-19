provider "aws" {
  region = var.aws_region
}

resource "aws_instance" "dev_instance_new" {
  ami           = var.ami_id
  instance_type = "t2.micro"
  vpc_security_group_ids = ["default"]
  subnet_id     = "${aws_subnet.default.id}"
  tags = {
    Name = "Development Instance New"
  }
}

resource "aws_instance" "dev_instance" {
  ami           = var.ami_id
  instance_type = "t2.micro"
  tags = {
    Name = "dev-instance"
  }
  
  # Use default security group
  vpc_security_group_ids = [aws_security_group.allow_ssh.id]

  # Specify the development environment
  environment = "development"
}

resource "aws_instance" "new_instance" {
  ami           = var.ami_id
  instance_type = var.instance_type
  tags = {
    Name = var.name
  }
}

resource "aws_instance" "example" {
  ami           = "ami-0c55b159cbfafe1f0"  # Amazon Linux 2 AMI
  instance_type = "t2.micro"
  subnet_id     = "${var.subnet_id}"
}

variable "subnet_id" {
  description = "The subnet ID where the instance will be launched"
  default     = "subnet-12345678"  # Default subnet
}

resource "aws_instance" "new_ec2" {
  ami           = "ami-0c55b159cbfafe1f0"  # Amazon Linux 2 AMI
  instance_type = "t2.micro"
  subnet_id     = "${aws_subnet.default.id}"

  vpc_security_group_ids = ["${aws_security_group.allow_ssh.id}"]

  tags = {
    Name = "NewEC2Instance"
  }
}

resource "aws_security_group" "allow_ssh" {
  vpc_id = "${aws_vpc.default.id}"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["192.168.1.1/32"]  # Replace with your actual IP address
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_subnet" "default" {
  vpc_id            = "${aws_vpc.default.id}"
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-east-1a"
}

resource "aws_vpc" "default" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_instance" "new_ec2_instance" {
  ami           = var.ami_id
  instance_type = var.instance_type
  tags = {
    Name = var.name
  }
}

resource "aws_instance" "new_instance" {
  ami           = var.ami_id
  instance_type = var.instance_type
  tags = {
    Name = "${var.name}-new-instance"
  }
}
}

resource "aws_key_pair" "development_key" {
  key_name   = "development_key"
  public_key = file("~/.ssh/id_rsa.pub")
}

resource "aws_instance" "dev_instance" {
  ami           = var.dev_ami_id
  instance_type = "t2.micro"
  key_name      = aws_key_pair.development_key.key_name
  tags = {
    Name = "DevelopmentInstance"
  }
}

resource "aws_instance" "my_ec2" {
  ami           = var.ami_id
  instance_type = var.instance_type

  tags = {
    Name = var.name
  }
}

resource "aws_instance" "dev_instance" {
  ami           = var.ami_id
  instance_type = "t2.micro"
  tags = {
    Name = "Development Instance"
  }
  
  # Use default security group
  vpc_security_group_ids = ["default"]
  
  # No key pair
  key_name = ""
}

resource "aws_instance" "ec2_instance_1" {
  ami           = "ami-0c55b159cbfafe1f0"  # Default AMI ID for t2.micro in the selected region
  instance_type = "t2.micro"
  
  tags = {
    Name = "ec2-instance-1"
  }

  # Use default security group
  vpc_security_group_ids = ["default"]

  # Use default IAM role
  iam_instance_profile = "default"
}

resource "aws_instance" "project_name_dev_t2_micro" {
  ami           = "ami-0c55b159cbfafe1f0"  # Amazon Linux 2 AMI ID for us-east-1
  instance_type = "t2.micro"

  # Use an existing security group
  vpc_security_group_ids = ["sg-0123456789abcdef0"]  # Replace with actual security group ID

  # Use an existing VPC
  subnet_id = "subnet-0123456789abcdef0"  # Replace with actual subnet ID

  # Key pair for SSH access
  key_name = "my-key-pair"  # Replace with actual key pair name

  tags = {
    Name        = "project-name-development-t2-micro"
    Environment = "Development"
    Project     = "XYZ"
  }
}

resource "aws_instance" "new_instance" {
  ami           = var.ami_id
  instance_type = var.instance_type
  tags = {
    Name = "NewInstance"
  }
}
