import os
import re
import base64
import requests
import csv
from io import StringIO
from urllib.parse import unquote
from github import Github
import random  # <<< 新增：导入 random 模块 >>>

# --- 1. 配置和环境变量部分 (无改动) ---
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")
FILE_PATH = os.getenv("FILE_PATH")
WEBPAGE_URLS = os.getenv("WEBPAGE_URLS", "").strip().splitlines()

COUNTRY_ORDER_STR = os.getenv("COUNTRY_ORDER") or ""
COUNTRY_ORDER = [code.strip() for code in COUNTRY_ORDER_STR.split(',')] if COUNTRY_ORDER_STR else []

# 您可以在 GitHub Secrets 中将此值设为 3
LINKS_PER_COUNTRY = int(os.getenv("LINKS_PER_COUNTRY") or "20")
LINK_PREFIX = os.getenv("LINK_PREFIX") or ""
LINK_SUFFIX = os.getenv("LINK_SUFFIX") or ""

# --- 2. 检查、常量和所有解析函数 (与上一版 V8 完全相同, 此处省略) ---
# ... (所有解析函数和主流程函数 process_subscription_url 等均无任何改动)
if not GITHUB_TOKEN or not REPO_NAME or not FILE_PATH: exit(1)
if not WEBPAGE_URLS: exit(1)
def extract_vless_links(decoded_content):
    COUNTRY_MAPPING = {
    "香港": "HK", "澳门": "MO", "台湾": "TW", "韩国": "KR", "日本": "JP",
    "新加坡": "SG", "美国": "US", "英国": "GB", "法国": "FR", "德国": "DE",
    "加拿大": "CA", "澳大利亚": "AU", "意大利": "IT", "荷兰": "NL", "挪威": "NO",
    "芬兰": "FI", "瑞典": "SE", "丹麦": "DK", "立тов": "LT", "俄罗斯": "RU",
    "印度": "IN", "土耳其": "TR", "捷克": "CZ", "爱沙尼亚": "EE", "拉脱维亚": "LV",
    "都柏林": "IE", "西班牙": "ES", "奥地利": "AT", "罗马尼亚": "RO", "波兰": "PL"
}
    regex = re.compile(r'(vless|vmess)://[a-zA-Z0-9\-]+@([^:]+):(\d+)\?[^#]+#([^\n\r]+)')
    links = []
    for match in regex.finditer(decoded_content):
        ip, port, country_name_raw = match.group(2), match.group(3), unquote(match.group(4).strip())
        country_code = "UNKNOWN"
        for name, code in COUNTRY_MAPPING.items():
            if name in country_name_raw: country_code = code; break
        else:
            code_match = re.search(r'([A-Z]{2})', country_name_raw)
            if code_match: country_code = code_match.group(1)
        
        if country_code != "UNKNOWN":
            formatted_link = f"{ip}:{port}#{LINK_PREFIX}{country_code}{LINK_SUFFIX}"
            links.append({"link": formatted_link, "code": country_code})
    return links
def extract_csv_links(csv_content):
    links = []
    f = StringIO(csv_content)
    reader = csv.reader(f)
    try:
        next(reader)
        for row in reader:
            if len(row) >= 4:
                ip, port, code = row[0].strip(), row[1].strip(), row[3].strip()
                if ip and port and code:
                    formatted_link = f"{ip}:{port}#{LINK_PREFIX}{code}{LINK_SUFFIX}"
                    links.append({"link": formatted_link, "code": code})
    except Exception as e:
        print(f"  > CSV 解析时出错: {e}")
    return links
def extract_line_based_links(plain_content):
    links = []
    for line in plain_content.strip().splitlines():
        clean_line = line.strip()
        if not clean_line: continue
        trojan_match = re.search(r'trojan://[^@]+@([^:]+):(\d+)[^#]*#(.+)', clean_line)
        if trojan_match:
            host, port, code = trojan_match.group(1), trojan_match.group(2), trojan_match.group(3).strip()
            formatted_link = f"{host}:{port}#{LINK_PREFIX}{code}{LINK_SUFFIX}"
            links.append({"link": formatted_link, "code": code})
            continue
        ip_port_match = re.search(r'([^:]+:\d+)#(.+)', clean_line)
        if ip_port_match:
            link_part, code = ip_port_match.group(1), ip_port_match.group(2).strip()
            formatted_link = f"{link_part}#{LINK_PREFIX}{code}{LINK_SUFFIX}"
            links.append({"link": formatted_link, "code": code})
    return links
def process_subscription_url(url):
    print(f"正在处理 URL: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        raw_content = response.text
        try:
            base64_content = "".join(raw_content.split())
            missing_padding = len(base64_content) % 4
            if missing_padding: base64_content += '=' * (4 - missing_padding)
            decoded_bytes = base64.b64decode(base64_content)
            decoded_text = decoded_bytes.decode('utf-8')
            print("  > 检测到 Base64 格式，使用 vless/vmess 解析器。")
            return extract_vless_links(decoded_text)
        except Exception: pass
        first_line = raw_content.strip().splitlines()[0] if raw_content.strip() else ""
        if ',' in first_line and "地址" in first_line:
            print("  > 检测到 CSV 格式，使用 CSV 解析器。")
            return extract_csv_links(raw_content)
        print("  > 未知格式，使用通用的行解析器。")
        return extract_line_based_links(raw_content)
    except requests.RequestException as e:
        print(f"  > 获取 URL 内容失败: {e}")
        return []

# --- 排序和写入函数 ---

# <<< 修改点 START >>>
def filter_and_sort_links(all_links, order, limit):
    """
    根据给定的顺序对链接进行分组，并从每组中【随机】抽取指定数量的链接。
    """
    grouped_links = {}
    for link_info in all_links:
        code = link_info['code']
        if code not in grouped_links: grouped_links[code] = []
        grouped_links[code].append(link_info['link'])
    
    order_to_use = order if order else list(grouped_links.keys())
    
    sorted_and_filtered_links = []
    for code in order_to_use:
        if code in grouped_links:
            unique_links = list(dict.fromkeys(grouped_links[code]))
            
            # --- 核心修改：从切片改为随机抽样 ---
            # 确定要抽样的数量 k，不能超过拥有的节点数
            num_to_sample = min(limit, len(unique_links))
            # 从该国家的节点中随机抽取 k 个
            randomly_selected = random.sample(unique_links, num_to_sample)
            
            sorted_and_filtered_links.extend(randomly_selected)
            # --- 原代码：sorted_and_filtered_links.extend(unique_links[:limit]) ---

    return sorted_and_filtered_links
# <<< 修改点 END >>>

def write_to_github(content):
    # ... (此函数无任何改动)
    if not content:
        print("没有生成任何内容，已跳过写入 GitHub。")
        return
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        try:
            file = repo.get_contents(FILE_PATH, ref="main")
            repo.update_file(path=FILE_PATH, message="Update subscription links", content=content, sha=file.sha, branch="main")
            print(f"文件 {FILE_PATH} 已在仓库 {REPO_NAME} 中成功更新。")
        except Exception:
            repo.create_file(path=FILE_PATH, message="Create subscription links file", content=content, branch="main")
            print(f"文件 {FILE_PATH} 已在仓库 {REPO_NAME} 中成功创建。")
    except Exception as e:
        print(f"写入 GitHub 时发生错误: {e}")

def main():
    # ... (此函数无任何改动)
    print("开始执行订阅链接处理任务...")
    all_extracted_links = []
    for url in WEBPAGE_URLS:
        if url:
            links = process_subscription_url(url)
            if links:
                all_extracted_links.extend(links)
    
    print(f"\n从所有源共提取了 {len(all_extracted_links)} 个有效链接。")

    if not all_extracted_links:
        print("未能从任何源提取到链接，任务终止。")
        return

    final_links = []
    if COUNTRY_ORDER:
        print("检测到 COUNTRY_ORDER, 进入排序分组模式...")
        final_links = filter_and_sort_links(all_extracted_links, COUNTRY_ORDER, LINKS_PER_COUNTRY)
    else:
        print("未检测到 COUNTRY_ORDER, 进入原始顺序模式...")
        final_links = [link_info['link'] for link_info in all_extracted_links]

    print(f"经过处理后，最终保留 {len(final_links)} 个链接。")
    final_content = "\n".join(final_links)
    write_to_github(final_content)

if __name__ == "__main__":
    main()
