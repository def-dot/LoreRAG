"""模型下载测试"""
import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from huggingface_hub import snapshot_download

def trigger_download():
    repo_id = "ibm-granite/granite-vision-4.1-4b"
    print(f"正在启动下载模型: {repo_id} ...")
    print("下载完成后会保存在系统的默认缓存目录中。")
    
    # 2. 触发完整下载
    local_dir = snapshot_download(
        repo_id=repo_id,
        resume_download=True,
        revision="dd48e97503de471803850df70843cf9eb5da8712"
    )
    
    print("\n" + "="*40)
    print("✨ 下载成功！")
    print(f"模型已完整保存至本地缓存路径:\n{local_dir}")
    print("="*40)

if __name__ == "__main__":
    trigger_download()
