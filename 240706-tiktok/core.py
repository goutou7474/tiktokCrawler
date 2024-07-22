import base64
import time
from bs4 import BeautifulSoup
from utils.crawler_util import get_user_agent
from utils import Logger
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_async
import random
import os
from datetime import datetime, timedelta
import csv
import re
import requests
import json
from tqdm import tqdm


def identify_captcha(api_key, verify_idf_id, base64_1, base64_2):
    url = "https://www.detayun.cn/openapi/verify_code_identify/"
    header = {"Content-Type": "application/json"}
    data = {
        "key": api_key,
        "verify_idf_id": verify_idf_id,
        "img1": base64_1,
        "img2": base64_2
    }

    response = requests.post(url=url, json=data, headers=header)
    return response.text


def drag_slider(page, slider_selector, distance):
    try:
        slider = page.locator(slider_selector)
        box = slider.bounding_box()
        if not box:
            raise Exception("Could not locate the slider element")

        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(box["x"] + box["width"] / 2 + distance, box["y"] + box["height"] / 2, steps=10)
        page.mouse.up()
    except:
        Logger.logger.info('Try second slider')


def save_image_as_base64(url, filename):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            # 保存图片
            with open(filename, 'wb') as file:
                file.write(response.content)

            # 读取图片内容并转换为 base64
            with open(filename, 'rb') as file:
                image_data = file.read()
                base64_encoded = base64.b64encode(image_data).decode('utf-8')

            return base64_encoded
        else:
            print(f"无法下载图片: {url}")
            return None
    except Exception as e:
        Logger.logger.info("[TikTokCrawler.error] TikTok Crawler error {e}".format(e=e))

def format_date(date_str):
    today = datetime.today()
    current_year = today.year

    if '分钟' in date_str:
        return today.strftime('%Y-%m-%d')
    elif '小时' in date_str:
        return today.strftime('%Y-%m-%d')
    elif '天' in date_str:
        days_ago = int(date_str.split('天')[0])
        date = today - timedelta(days=days_ago)
        return date.strftime('%Y-%m-%d')
    else:
        # 检查是否包含年份
        if '-' in date_str:
            parts = date_str.split('-')
            if len(parts[0]) == 4:
                # 包含年份，直接格式化
                date = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                # 没有年份，加上今年的年份
                date_str = f'{current_year}-{date_str}'
                date = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            Logger.logger.info(f"error for format date: {date_str}")
            # 格式不对，返回None
            return None
        return date.strftime('%Y-%m-%d')

def generate_filename():
    # 确保 data 文件夹存在
    if not os.path.exists('data'):
        os.makedirs('data')

    # 获取今天的日期
    today_date = datetime.now().strftime('%Y%m%d')

    # 获取当前最大的文件序号
    max_index = 0
    for filename in os.listdir('data'):
        if filename.startswith(today_date):
            file_index = int(filename.split('_')[1])
            max_index = max(max_index, file_index)

    # 确定新文件的序号
    new_index = max_index + 1

    # 文件名
    filename = f"{today_date}_{new_index}_comments.csv"
    filepath = os.path.join('data', filename)

    return filepath

class TikTokCrawler:
    def __init__(self, headless, target_date):
        self.user_agent = get_user_agent()
        self.headless = headless
        self.target_date = target_date
        self.target_date_obj = datetime.strptime(target_date, '%Y-%m-%d')

    def main(self, TIKTOK_USERS_URL_LIST):
        with sync_playwright() as p:
            # Launch Chromium browser
            chromium = p.chromium
            self.browser_context = self.launch_browser(
                chromium,
                # playwright_proxy_format,
                self.user_agent,
                headless=self.headless
            )

            # Add stealth script to prevent detection
            self.browser_context.add_init_script(path="utils/stealth.min.js")

            # Create a new page and navigate to the index URL
            self.context_page = self.browser_context.new_page()
            stealth_async(self.context_page)
            filepath = generate_filename()
            with open(filepath, mode='w', newline='', encoding='utf-8') as file:
                fieldnames = ['video_desc', 'video_launch_time', 'video_url', 'comment_id', 'parent_comment_id',
                              'comment_time', 'comment_content', 'commenter_name', 'commenter_space']
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
            Logger.logger.info("[TikTokCrawler.start] TikTok Crawler geting user's video")
            for i, url in enumerate(tqdm(TIKTOK_USERS_URL_LIST, desc="Processing users")):
                # 你的处理代码
                print(f"正在处理第 {i + 1} 个 user: {url}")
                video_url_list = self.get_users_video_url(url)
                if video_url_list:
                    self.start_crawling(video_url_list, filepath)
                else:
                    continue
    def get_users_video_url(self, url):
        # 首次进入博主页面
        time.sleep(5)  # 等待页面加载
        self.handle_captcha()
        # 初次滚动两次以加载更多视频
        self.scroll_and_load_more_videos(6)
        self.handle_captcha()
        # 初次获取视频URL
        video_url_list = self.load_video_urls()
        is_in, video_url_list = self.check_videos(video_url_list)
        # 检查初次获取的视频日期
        if is_in:
            # 如果所有视频都在日期范围内，则继续加载更多视频
            tmp_i = 2
            previous_num = len(video_url_list)
            while True:
                self.context_page.goto(url)
                time.sleep(5)  # 等待页面加载
                self.handle_captcha()
                self.scroll_and_load_more_videos(tmp_i * 6)
                self.handle_captcha()
                new_video_urls = self.load_video_urls()
                new_num = len(new_video_urls)
                is_in, video_url_list = self.check_videos(new_video_urls)
                if is_in and (previous_num != new_num):
                    tmp_i += 1
                    previous_num = new_num
                    continue
                else:
                    print(video_url_list)
                    return video_url_list
        else:
            print(video_url_list)
            return video_url_list

    def load_video_urls(self):
        time.sleep(5)
        video_url_list = []

        video_list_str = self.context_page.query_selector('div[class*="DivVideoFeedV2"]')
        if video_list_str:
            video_list_html = self.context_page.evaluate('element => element.outerHTML', video_list_str)
        else:
            print("Failed to find the video section， 可能网络不佳，正在重新尝试")
            return []

        soup = BeautifulSoup(video_list_html, 'lxml')
        video_list = soup.select(
            'div[class*="DivItemContainerV2"] > div[class*="DivContainer"] > div > div[class*="DivWrapper"] > a')
        if video_list:
            for video in video_list:
                href = video.get('href')
                if href not in video_url_list:  # Avoid duplicates
                    video_url_list.append(href)
        print(f"Loaded video URLs: {video_url_list}")
        return video_url_list

    def start_crawling(self, TIKTOK_SPECIFIED_URL_LIST, filepath):
        Logger.logger.info("[TikTokCrawler.start] TikTok Crawler start ...")
        for url in tqdm(TIKTOK_SPECIFIED_URL_LIST, desc="Processing URLs"):
            try:
                self.context_page.goto(url)
                time.sleep(5)  # 等待页面加载
                self.context_page.wait_for_selector('div[class*="DivCommentContainer"]', timeout=30000)
                self.handle_captcha()
                self.context_page.wait_for_selector('div[class*="DivCommentListContainer"]', timeout=60000)
                self.handle_captcha()
                comment_container = self.context_page.query_selector('div[class*="DivCommentContainer"]')
                comment_title = comment_container.query_selector('p[class*="PCommentTitle"]')
                comment_text = comment_title.inner_text()
                comment_count = int(comment_text.split(' ')[0])
                print(f"This video's comment num is {comment_count}")

                time_selector = 'span[class*="SpanOtherInfos"] > span:last-child'
                self.context_page.wait_for_selector(time_selector)
                time_text = self.context_page.locator(time_selector).inner_text().replace(" ", "")
                video_launch_time = format_date(time_text)
                video_date_obj = datetime.strptime(video_launch_time, '%Y-%m-%d')
                if video_date_obj < self.target_date_obj or comment_count == 0:
                    continue

                self.crawl_comments(filepath, comment_count)
            except Exception as e:
                Logger.logger.info("[TikTokCrawler.error] TikTok Crawler error {e}".format(e=e))
                continue
        Logger.logger.info(f"[TikTokCrawler.start] TikTok Crawler finish,data saved in {filepath}")

    def crawl_comments(self, filepath, comment_count):
        # 写入 CSV 文件
        if comment_count < 30:
            scroll_num = 1
        elif comment_count < 100:
            scroll_num = 2
        else:
            scroll_num = 3
        MAX_NO_CHANGE_ATTEMPTS = scroll_num
        with open(filepath, mode='a', newline='', encoding='utf-8') as file:
            fieldnames = ['video_desc', 'video_launch_time', 'video_url', 'comment_id', 'parent_comment_id',
                          'comment_time', 'comment_content', 'commenter_name', 'commenter_space']

            writer = csv.DictWriter(file, fieldnames=fieldnames)
            current_url = self.context_page.url
            comment_selector = 'div[class*="DivCommentItemContainer"]'  # 更新后的选择器
            comment_container_selector = 'div[class*="DivCommentListContainer"]'
            # 初始评论计数
            last_comments = self.context_page.query_selector_all(comment_selector)
            no_change_attempts = 0
            while True:
                self.handle_captcha()
                while True:
                    # 每次加载更多内容后，查找并点击所有的下拉图标

                    icons = self.context_page.query_selector_all('svg.css-1w2nwdz-StyledChevronDownFill')
                    if not icons:
                        break  # 如果没有找到按钮，跳出循环
                    for icon in icons:
                        try:
                            icon.hover()
                            icon.click()
                            time.sleep(random.uniform(0.5, 1))  # 给页面一点时间来处理每个点击
                        except Exception as e:
                            print(f"An error occurred while clicking a check-more-reply button: {e}")
                            break

                for _ in range(scroll_num):  # 假设我们滚动10次
                    self.context_page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    self.context_page.wait_for_timeout(0.1)  # 每次滚动后等待1秒

                time.sleep(2.5)
                current_comments = self.context_page.query_selector_all(comment_selector)
                if len(current_comments) == len(last_comments):
                    no_change_attempts += 1
                    print(f"No change detected, attempt {no_change_attempts}")
                    time.sleep(no_change_attempts / 6)
                else:
                    no_change_attempts = 0  # 重置无变化尝试次数
                    last_comments = current_comments  # 更新评论列表
                    print(f"New comments loaded, total comments: {len(current_comments)}")

                if no_change_attempts >= MAX_NO_CHANGE_ATTEMPTS:
                    print("No more comments to load.")
                    break

            self.context_page.wait_for_selector('h1[data-e2e*="browse-video-desc"]')
            video_desc_element = self.context_page.query_selector('h1[data-e2e*="browse-video-desc"] span')
            video_desc = video_desc_element.inner_text() if video_desc_element else "Element not found"

            time_selector = 'span[class*="SpanOtherInfos"] > span:last-child'
            self.context_page.wait_for_selector(time_selector)
            time_text = self.context_page.locator(time_selector).inner_text().replace(" ", "")
            video_launch_time = format_date(time_text)

            comment_section = self.context_page.query_selector('div[class*="DivCommentListContainer"]')
            if comment_section:
                comment_section_html = self.context_page.evaluate('element => element.outerHTML', comment_section)
            else:
                print("Failed to find the comment section.")

            soup = BeautifulSoup(comment_section_html, 'lxml')
            # 找到所有一级评论
            primary_comments = soup.select('div[class*="DivCommentItemContainer"]')  # Adjusted selector
            extracted_comments = []
            for index, comment in enumerate(primary_comments):
                top_comment = comment.select_one('div[class*="DivCommentContentContainer"]')
                top_comment_id = top_comment.get('id')
                top_parent_comment_id = top_comment_id
                top_comment_time_str = top_comment.find('span', class_=re.compile(r'SpanCreatedTime')).text
                top_comment_content = top_comment.find('p', class_=re.compile(r'PCommentText')).text.replace('\n',
                                                                                                             '').replace(
                    '\r', '').replace('\t', '')
                user_link = top_comment.find('a', class_=re.compile(r'StyledUserLinkName'))
                user_href = user_link.get('href')
                user_name = user_link.find('span').text
                extracted_comment = {
                    'video_desc': video_desc,
                    'video_launch_time': video_launch_time,
                    'video_url': current_url,
                    'comment_id': top_comment_id,
                    'parent_comment_id': top_parent_comment_id,
                    'comment_time': top_comment_time_str,
                    'comment_content': top_comment_content,
                    'commenter_name': user_name,
                    'commenter_space': f"https://www.tiktok.com{user_href}"
                }

                writer.writerow(extracted_comment)
                extracted_comments.append(extracted_comment)
                Logger.logger.info(
                    f"[TikTokCrawler.crawling] TikTok Crawler crawls comment {extracted_comment['comment_content']}")

                sub_comment_num = len(comment.find_all('div', class_=re.compile(r'DivReplyContainer')))

                if sub_comment_num > 0:
                    sub_comment_section = comment.select_one('div[class*="DivReplyContainer"]')
                    soup = BeautifulSoup(str(sub_comment_section), 'lxml')
                    # 找到所有二级评论
                    secondary_comments = soup.select('div[class*="DivCommentContentContainer"]')  # Adjusted selector
                    for sub_comment in secondary_comments:
                        if 'DivCommentContentContainer' in sub_comment.get('class', []):
                            comment_id = sub_comment.get('id')
                            parent_comment_id = top_parent_comment_id
                            comment_time_str = sub_comment.find('span', class_=re.compile(r'SpanCreatedTime')).text
                            comment_content = sub_comment.find('p', class_=re.compile(r'PCommentText')).text.replace(
                                '\n', '').replace('\r', '').replace('\t', '')
                            user_link = sub_comment.find('a', class_=re.compile(r'StyledUserLinkName'))
                            user_href = user_link.get('href')
                            user_name = user_link.find('span').text
                            extracted_comment = {
                                'video_desc': video_desc,
                                'video_launch_time': video_launch_time,
                                'video_url': current_url,
                                'comment_id': comment_id,
                                'parent_comment_id': parent_comment_id,
                                'comment_time': comment_time_str,
                                'comment_content': comment_content,
                                'commenter_name': user_name,
                                'commenter_space': f"https://www.tiktok.com{user_href}"
                            }
                            writer.writerow(extracted_comment)
                            extracted_comments.append(extracted_comment)
                            Logger.logger.info(
                                f"[BaijiahaoCrawler.crawling] Baijiahao Crawler crawls comment {extracted_comment['comment_content']}")
            time.sleep(3)
        return extracted_comments if extracted_comments else []

    def handle_captcha(self):
        # 检查滑动验证码是否出现
        captcha_container = self.context_page.query_selector('div.captcha_verify_container')
        if captcha_container and captcha_container.get_attribute(
                'style') and 'visibility: visible' in captcha_container.get_attribute('style'):
            print("滑动验证码已出现")

            # 获取 outer img 和 inner img 的 URL
            outer_img = self.context_page.query_selector('img[data-testid="whirl-outer-img"]')
            inner_img = self.context_page.query_selector('img[data-testid="whirl-inner-img"]')

            if outer_img and inner_img:
                outer_img_url = outer_img.get_attribute('src')
                inner_img_url = inner_img.get_attribute('src')

                # 保存图片并转换为 base64 编码
                outer_img_base64 = save_image_as_base64(outer_img_url, 'outer_img.jpeg')
                inner_img_base64 = save_image_as_base64(inner_img_url, 'inner_img.jpeg')
                if (outer_img_base64 is None) or (inner_img_base64 is None):
                    self.context_page.reload()
                    time.sleep(6)
                else:
                    text = identify_captcha("Mtej5eME6t7vwc5eHCLR", "37", f"data:image/jpeg;base64,{outer_img_base64}",
                                            f"data:image/jpeg;base64,{inner_img_base64}")
                    data = json.loads(text)
                    # 获取px_distance的值
                    px_distance = data['data']['px_distance']
                    print(text, px_distance)
                    drag_slider(self.context_page, '.secsdk-captcha-drag-icon', px_distance)
            else:
                print("未找到 outer img 或 inner img")
                self.context_page.reload()
                time.sleep(6)
        else:
            print("滚动验证码未出现")

    def scroll_and_load_more_videos(self, scroll_times):
        for _ in range(scroll_times):  # 根据传入的次数滚动
            self.context_page.evaluate('window.scrollTo(0, document.body.scrollHeight);')
            time.sleep(3)  # 等待页面加载

    def check_videos(self, video_url_list):
        video_url_result = []
        for i in range(0, len(video_url_list), 15):
            url = video_url_list[i]
            self.context_page.goto(url)
            time_selector = 'span[class*="SpanOtherInfos"] > span:last-child'
            self.context_page.wait_for_selector(time_selector)
            time_text = self.context_page.locator(time_selector).inner_text().replace(" ", "")
            format_time = format_date(time_text)
            print(f"URL: {url} -> Date: {format_time}")

            if format_time is None:
                continue

            video_date_obj = datetime.strptime(format_time, '%Y-%m-%d')

            if video_date_obj < self.target_date_obj:
                print(
                    f"Removing URLs after index {i} since date {format_time} is before target date {self.target_date}")
                video_url_result = video_url_list[:i]
                break
            else:
                video_url_result = video_url_list

        if len(video_url_result) == len(video_url_list):
            return True, video_url_result
        else:
            return False, video_url_result

    def launch_browser(self, chromium, user_agent, headless=True):
        browser = chromium.launch(headless=headless)
        context = browser.new_context(user_agent=user_agent)
        return context

