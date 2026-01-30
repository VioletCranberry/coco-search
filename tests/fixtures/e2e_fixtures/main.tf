resource "aws_instance" "web_server" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t2.micro"

  tags = {
    Name        = "WebServer"
    Environment = "production"
  }
}

output "instance_ip" {
  value = aws_instance.web_server.public_ip
}
