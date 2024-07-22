import pandas as pd
import os

pd.set_option('display.max_columns', None)  # 设置显示无限制的列数
pd.set_option('display.max_colwidth', None)  # 设置列宽度无限制

def get_csv_files_from_folder(folder_path):
    csv_files = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if file.endswith('.csv')]
    return csv_files

def search_comments(paths, keywords, is_folder=False):
    if isinstance(paths, str):
        paths = [paths]
    if isinstance(keywords, str):
        keywords = [keywords]

    all_comments = pd.DataFrame()

    if is_folder:
        csv_files = []
        for path in paths:
            csv_files.extend(get_csv_files_from_folder(path))
    else:
        csv_files = paths

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        all_comments = pd.concat([all_comments, df], ignore_index=True)

    matched_comments = []

    for keyword in keywords:
        matches = all_comments[all_comments['comment_content'].str.contains(keyword, na=False, case=False)]
        matched_comments.append(matches)

    matched_comments_df = pd.concat(matched_comments).drop_duplicates()

    for _, row in matched_comments_df.iterrows():
        print("-" * 200)
        print("匹配到的评论:")
        print("*" * 50)
        print(row)
        print("*" * 50)
        print("-" * 200)

# Example usage
# 使用文件路径
# csv_files = ['data/20240722_2_comments.csv', 'data/20240722_3_comments.csv','data/20240722_4_comments.csv']
# keywords = ['多少', '想']
# search_comments(csv_files, keywords, is_folder=False)

# 使用文件夹路径
folder_paths = ['data/']
keywords = ['多少', '想']
search_comments(folder_paths, keywords, is_folder=True)
