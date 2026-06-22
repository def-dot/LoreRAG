import os
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from typing import List, Dict, Any

class LocalReranker:
    def __init__(self, model_path: str):
        """
        model_path: 本地模型文件夹的路径，例如 "D:/models/bge-reranker-large" 或 "./models/bge-reranker-large"
        """
        # 规范化路径，防止 Windows/Linux 环境下的斜杠问题
        self.model_path = os.path.abspath(model_path)
        
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"找不到本地模型目录: {self.model_path}")
            
        # 设备选择
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
        elif torch.backends.mps.is_available():
            self.device = torch.device("mps")
        else:
            self.device = torch.device("cpu")
            
        print(f"正在从本地路径加载模型: {self.model_path} -> 运行在 {self.device} 上")
        
        # 核心改动：传入本地路径，并开启 local_files_only=True 强制纯本地加载
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path, 
            local_files_only=True
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_path, 
            local_files_only=True
        )
        
        self.model.to(self.device)
        self.model.eval()

    def rerank(self, query: str, documents: List[str], top_n: int = 5) -> List[Dict[str, Any]]:
        if not documents:
            return []

        pairs = [[query, doc] for doc in documents]
        
        with torch.no_grad():
            inputs = self.tokenizer(
                pairs, 
                padding=True, 
                truncation=True, 
                max_length=512, 
                return_tensors="pt"
            ).to(self.device)
            
            outputs = self.model(**inputs, return_dict=True)
            scores = outputs.logits.view(-1).float().cpu().tolist()

        results = [
            {"index": i, "document": documents[i], "score": score} 
            for i, score in enumerate(scores)
        ]
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]

# 💡 本地调用测试
if __name__ == "__main__":
    # 替换为你实际存放模型的本地路径
    MY_LOCAL_MODEL_PATH = "./hub/bge-reranker-v2-m3" 
    
    reranker = LocalReranker(model_path=MY_LOCAL_MODEL_PATH)
    
    query = "如何离线加载模型"
    docs = [
        "把 from_pretrained 里的字符串换成本地路径，并加上 local_files_only=True 即可。",
        "今天中午打算吃个番茄炒蛋和香煎大虾。",
    ]
    
    print(reranker.rerank(query, docs, top_n=2))