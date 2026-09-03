import os

# 单测不打真实 LLM，避免网络和费用
os.environ["POKERGYM_LLM"] = "0"
