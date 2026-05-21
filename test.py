import ipaddress
import random
from typing import List, Set


def is_subnet(child_cidr: str, parent_cidr: str) -> bool:
    try:
        child = ipaddress.ip_network(child_cidr)
        parent = ipaddress.ip_network(parent_cidr)
        
        # 判断 child 是否是 parent 的子集
        return child.subnet_of(parent)
    except ValueError as e:
        print(f"非法的 CIDR 格式: {e}")
        return False
    

r = is_subnet("192.168.0.0/16", "192.0.0.0/14")
print(r)