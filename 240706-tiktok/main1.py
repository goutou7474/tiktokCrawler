from core import TikTokCrawler

##这里放想要监控的博主主页链接
TIKTOK_USERS_URL_LIST = [
    "https://www.tiktok.com/@xiaoqiao33",
    "https://www.tiktok.com/@dubai_yangziyi",
    "https://www.tiktok.com/@user5753633180527",
    "https://www.tiktok.com/@owen1233211"
]
headless = True   #True看不到浏览器具体运行过程，但是速度快；False能看到浏览器运行过程，但是慢
test_crawler = TikTokCrawler(headless,'2024-1-1')
video_url_list = test_crawler.main(TIKTOK_USERS_URL_LIST)

