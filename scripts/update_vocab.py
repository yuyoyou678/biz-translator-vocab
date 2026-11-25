#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商务英语翻译器 - 词库自动更新脚本（供 GitHub Actions 云端每日执行）
逻辑：从 candidate_pool.json 中释放尚未收录的高质量词条到 vocab.json，
      递增版本号，更新 updatedAt。无新增时保持幂等退出。
词库全部为 self-curated 自编词条，不引入任何第三方词库数据，规避侵权。
"""
import json, os, sys, datetime, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOCAB_PATH = os.path.join(ROOT, 'vocab.json')
VERSION_PATH = os.path.join(ROOT, 'version.json')
POOL_PATH = os.path.join(ROOT, 'scripts', 'candidate_pool.json')
RELEASE_N = int(os.environ.get('RELEASE_N', '20'))  # 每次释放条数


def norm_ver(v):
    """返回 (日期部分YYYYMMDD, 序号)。兼容 20261125 / 2026112501 格式。"""
    s = str(v)
    m = re.match(r'^(\d{8})(\d*)$', s)
    if m:
        return m.group(1), int(m.group(2) or 0)
    return s, 0


def main():
    with open(VOCAB_PATH, encoding='utf-8') as f:
        vocab = json.load(f)
    with open(POOL_PATH, encoding='utf-8') as f:
        pool = json.load(f)

    # 现有中文键与英文键（用于去重，防止重复释放）
    cn_keys = set()
    en_keys = set()
    for t in vocab.get('terms', []):
        cn_keys.add(t[0])
        for v in str(t[1]).split('|'):
            en_keys.add(v.strip().lower())
    for t in vocab.get('phrases', []):
        cn_keys.add(t[0])

    today = datetime.date.today()
    date_str = today.strftime('%Y%m%d')
    iso_date = today.isoformat()

    # 筛选未收录词条
    fresh = [row for row in pool if row[0] not in cn_keys]
    # 进一步按英文去重
    fresh = [row for row in fresh if str(row[1]).split('|')[0].strip().lower() not in en_keys]

    if not fresh:
        print('NO_UPDATE: 候选池无新增词条（已全部收录或池空）')
        print('VERSION_UNCHANGED: %s' % vocab.get('version'))
        sys.exit(0)

    # 余量越少释放越慢，延长自动更新可持续时间
    release_n = RELEASE_N
    if len(fresh) < 20:
        release_n = 1
    elif len(fresh) < 60:
        release_n = 5
    elif len(fresh) < 140:
        release_n = 10
    batch = fresh[:release_n]
    for cn, en, cat in batch:
        vocab['terms'].append([cn, en, cat])

    # 版本号递增：同日期则序号+1，跨日期则用当天日期01
    d, seq = norm_ver(vocab.get('version'))
    if d == date_str:
        new_ver = '%s%02d' % (date_str, seq + 1)
    else:
        new_ver = date_str + '01'
    vocab['version'] = int(new_ver)
    vocab['updatedAt'] = iso_date
    if 'sources' not in vocab or not vocab['sources']:
        vocab['sources'] = ['self-curated']

    with open(VOCAB_PATH, 'w', encoding='utf-8') as f:
        json.dump(vocab, f, ensure_ascii=False, indent=1)
        f.write('\n')

    # 同步轻量版本文件（网页据此先探测版本，未变则不下载词库正文）
    with open(VERSION_PATH, 'w', encoding='utf-8') as f:
        json.dump({'version': vocab['version']}, f, ensure_ascii=False)
        f.write('\n')

    print('UPDATED: 新增 %d 条' % len(batch))
    print('NEW_VERSION: %s' % vocab['version'])
    print('TOTAL_TERMS: %d' % len(vocab['terms']))
    print('REMAINING_POOL: %d' % (len(fresh) - len(batch)))
    for cn, en, cat in batch:
        print('  + [%s] %s -> %s' % (cat, cn, en))


if __name__ == '__main__':
    main()
