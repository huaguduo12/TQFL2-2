import os
import re
import base64
import requests
import csv
from io import StringIO
from urllib.parse import unquote
from github import Github
import random

# --- 1. 配置读取 ---
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")
FILE_PATH = os.getenv("FILE_PATH")
WEBPAGE_URLS = os.getenv("WEBPAGE_URLS", "").strip().splitlines()

COUNTRY_ORDER_STR = os.getenv("COUNTRY_ORDER") or ""
COUNTRY_ORDER = [code.strip() for code in COUNTRY_ORDER_STR.split(',')] if COUNTRY_ORDER_STR else []

LINKS_PER_COUNTRY = int(os.getenv("LINKS_PER_COUNTRY") or "20")
LINK_PREFIX = os.getenv("LINK_PREFIX") or ""
LINK_SUFFIX = os.getenv("LINK_SUFFIX") or ""

# 新增：输出格式控制器 (simple/full)
OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT") or "full"

if not GITHUB_TOKEN or not REPO_NAME or not FILE_PATH: exit(1)
if not WEBPAGE_URLS: exit(1)

COUNTRY_MAPPING = {
    # 亚洲
    "香港": "HK", "澳门": "MO", "台湾": "TW", "中国": "CN", "大陆": "CN",
    "日本": "JP", "韩国": "KR", "新加坡": "SG", "马来西亚": "MY", "泰国": "TH",
    "越南": "VN", "菲律宾": "PH", "印度尼西亚": "ID", "印度": "IN", "孟加拉": "BD",
    "柬埔寨": "KH", "老挝": "LA", "缅甸": "MM", "尼泊尔": "NP", "巴基斯坦": "PK",
    "斯里兰卡": "LK", "土耳其": "TR", "阿联酋": "AE", "沙特": "SA", "以色列": "IL",
    "卡塔尔": "QA", "巴林": "BH", "科威特": "KW", "阿曼": "OM", "格鲁吉亚": "GE",
    "亚美尼亚": "AM", "阿塞拜疆": "AZ", "哈萨克斯坦": "KZ", "吉尔吉斯斯坦": "KG",
    "塔吉克斯坦": "TJ", "乌兹别克斯坦": "UZ",
    # 欧洲
    "英国": "GB", "法国": "FR", "德国": "DE", "荷兰": "NL", "瑞士": "CH",
    "俄罗斯": "RU", "乌克兰": "UA", "意大利": "IT", "西班牙": "ES", "葡萄牙": "PT",
    "瑞典": "SE", "挪威": "NO", "丹麦": "DK", "芬兰": "FI", "冰岛": "IS",
    "爱尔兰": "IE", "比利时": "BE", "卢森堡": "LU", "奥地利": "AT", "波兰": "PL",
    "捷克": "CZ", "匈牙利": "HU", "罗马尼亚": "RO", "保加利亚": "BG", "希腊": "GR",
    "爱沙尼亚": "EE", "拉脱维亚": "LV", "立陶宛": "LT", "白俄罗斯": "BY", "摩尔多瓦": "MD",
    "塞尔维亚": "RS", "克罗地亚": "HR", "斯洛文尼亚": "SI", "斯洛伐克": "SK",
    "波黑": "BA", "黑山": "ME", "阿尔巴尼亚": "AL", "北马其顿": "MK", "马耳他": "MT", "塞浦路斯": "CY",
    # 北美洲
    "美国": "US", "加拿大": "CA", "墨西哥": "MX",
    # 南美洲
    "巴西": "BR", "阿根廷": "AR", "哥伦比亚": "CO", "智利": "CL", "秘鲁": "PE",
    # 大洋洲
    "澳大利亚": "AU", "新西兰": "NZ",
    # 非洲
    "南非": "ZA", "埃及": "EG", "尼日利亚": "NG", "肯尼亚": "KE", "摩洛哥": "MA",
}
CODE_TO_NAME = {v: k for k, v in COUNTRY_MAPPING.items()}
CODE_TO_FLAG = {
    # 亚洲
    "HK": "🇭🇰", "MO": "🇲🇴", "TW": "🇹🇼", "CN": "🇨🇳", "JP": "🇯🇵", "KR": "🇰🇷",
    "SG": "🇸🇬", "MY": "🇲🇾", "TH": "🇹🇭", "VN": "🇻🇳", "PH": "🇵🇭", "ID": "🇮🇩",
    "IN": "🇮🇳", "BD": "🇧🇩", "KH": "🇰🇭", "LA": "🇱🇦", "MM": "🇲🇲", "NP": "🇳🇵",
    "PK": "🇵🇰", "LK": "🇱🇰", "TR": "🇹🇷", "AE": "🇦🇪", "SA": "🇸🇦", "IL": "🇮🇱",
    "QA": "🇶🇦", "BH": "🇧🇭", "KW": "🇰🇼", "OM": "🇴🇲", "GE": "🇬🇪", "AM": "🇦🇲",
    "AZ": "🇦🇿", "KZ": "🇰🇿", "KG": "🇰🇬", "TJ": "🇹🇯", "UZ": "🇺🇿",
    # 欧洲
    "GB": "🇬🇧", "FR": "🇫🇷", "DE": "🇩🇪", "NL": "🇳🇱", "CH": "🇨🇭", "RU": "🇷🇺",
    "UA": "🇺🇦", "IT": "🇮🇹", "ES": "🇪🇸", "PT": "🇵🇹", "SE": "🇸🇪", "NO": "🇳🇴",
    "DK": "🇩🇰", "FI": "🇫🇮", "IS": "🇮🇸", "IE": "🇮🇪", "BE": "🇧🇪", "LU": "🇱🇺",
    "AT": "🇦🇹", "PL": "🇵🇱", "CZ": "🇨🇿", "HU": "🇭🇺", "RO": "🇷🇴", "BG": "🇧🇬",
    "GR": "🇬🇷", "EE": "🇪🇪", "LV": "🇱🇻", "LT": "🇱🇹", "BY": "🇧🇾", "MD": "🇲🇩",
    "RS": "🇷🇸", "HR": "🇭🇷", "SI": "🇸🇮", "SK": "🇸🇰", "BA": "🇧🇦", "ME": "🇲🇪",
    "AL": "🇦🇱", "MK": "🇲🇰", "MT": "🇲🇹", "CY": "🇨🇾",
    # 北美洲
    "US": "🇺🇸", "CA": "🇨🇦", "MX": "🇲🇽",
    # 南美洲
    "BR": "🇧🇷", "AR": "🇦🇷", "CO": "🇨🇴", "CL": "🇨🇱", "PE": "🇵🇪",
    # 大洋洲
    "AU": "🇦🇺", "NZ": "🇳🇿",
    # 非洲
    "ZA": "🇿🇦", "EG": "🇪🇬", "NG": "🇳🇬", "KE": "🇰🇪", "MA": "🇲🇦",
    # 未知
    "UNKNOWN": "❓"
}

# --- 3. 链接提取函数 (无需改动) ---
def extract_vless_links(decoded_content):
    regex = re.compile(r'(vless|vmess)://[a-zA-Z0-9\-]+@([^:]+):(\d+)\?[^#]+#([^\n\r]+)')
    links = []
    for match in regex.finditer(decoded_content):
        ip, port, country_name_raw = match.group(2), match.group(3), unquote(match.group(4).strip())
        country_code = "UNKNOWN"
        # 使用更长的列表进行匹配
        for name, code in COUNTRY_MAPPING.items():
            if name in country_name_raw: country_code = code; break
        else:
            code_match = re.search(r'([A-Z]{2})', country_name_raw)
            if code_match: country_code = code_match.group(1)
        
        if country_code != "UNKNOWN":
            link_part = f"{ip}:{port}"
            links.append({"link_part": link_part, "code": country_code})
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
                    link_part = f"{ip}:{port}"
                    links.append({"link_part": link_part, "code": code})
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
            link_part = f"{host}:{port}"
            links.append({"link_part": link_part, "code": code})
            continue
        ip_port_match = re.search(r'([^:]+:\d+)#(.+)', clean_line)
        if ip_port_match:
            link_part, code = ip_port_match.group(1), ip_port_match.group(2).strip()
            links.append({"link_part": link_part, "code": code})
    return links

# --- 4. 核心处理逻辑 (无需改动) ---
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

def format_link(link_part, code, index=None):
    if OUTPUT_FORMAT == 'full':
        flag = CODE_TO_FLAG.get(code, CODE_TO_FLAG["UNKNOWN"])
        name = CODE_TO_NAME.get(code, code)
        name_suffix = str(index) if index is not None else ""
        return f"{link_part}#{LINK_PREFIX}{flag}{name}{name_suffix}{LINK_SUFFIX}"
    else:
        return f"{link_part}#{LINK_PREFIX}{code}{LINK_SUFFIX}"

def filter_and_sort_links(all_links, order, limit):
    grouped_links = {}
    for link_info in all_links:
        code = link_info['code']
        if code not in grouped_links: grouped_links[code] = []
        grouped_links[code].append(link_info['link_part'])
    
    order_to_use = order if order else list(grouped_links.keys())
    
    final_links = []
    for code in order_to_use:
        if code in grouped_links:
            unique_links = list(dict.fromkeys(grouped_links[code]))
            num_to_sample = min(limit, len(unique_links))
            randomly_selected = random.sample(unique_links, num_to_sample)
            
            for i, link_part in enumerate(randomly_selected, 1):
                final_links.append(format_link(link_part, code, i))
                
    return final_links

def write_to_github(content):
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

# --- 5. 主函数 (无需改动) ---
def main():
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
        print("检测到 COUNTRY_ORDER, 进入【随机排序】分组模式...")
        final_links = filter_and_sort_links(all_extracted_links, COUNTRY_ORDER, LINKS_PER_COUNTRY)
    else:
        print("未检测到 COUNTRY_ORDER, 进入原始顺序模式...")
        country_counters = {}
        for link_info in all_extracted_links:
            code = link_info['code']
            link_part = link_info['link_part']
            
            current_count = country_counters.get(code, 0) + 1
            country_counters[code] = current_count
            
            final_links.append(format_link(link_part, code, current_count))

    print(f"经过处理后，最终保留 {len(final_links)} 个链接。")
    final_content = "\n".join(final_links)
    write_to_github(final_content)

if __name__ == "__main__":
    main()
