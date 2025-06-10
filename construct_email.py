from paper import ArxivPaper
import math
from tqdm import tqdm
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
import smtplib
import datetime
from loguru import logger
from collections import defaultdict

framework = """
<!DOCTYPE HTML>
<html>
<head>
  <style>
    .star-wrapper {
      font-size: 1.3em; /* 调整星星大小 */
      line-height: 1; /* 确保垂直对齐 */
      display: inline-flex;
      align-items: center; /* 保持对齐 */
    }
    .half-star {
      display: inline-block;
      width: 0.5em; /* 半颗星的宽度 */
      overflow: hidden;
      white-space: nowrap;
      vertical-align: middle;
    }
    .full-star {
      vertical-align: middle;
    }
  </style>
</head>
<body>

<div>
    __CONTENT__
</div>

<br><br>
<div>
To unsubscribe, remove your email in your Github Action setting.
</div>

</body>
</html>
"""

def get_empty_html():
  block_template = """
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
  <tr>
    <td style="font-size: 20px; font-weight: bold; color: #333;">
        No Papers Today. Take a Rest!
    </td>
  </tr>
  </table>
  """
  return block_template

def get_block_html(title:str, authors:str, rate:str,arxiv_id:str, abstract:str, pdf_url:str, code_url:str=None, affiliations:str=None, category:str=None, matched_keywords=None):
    code = f'<a href="{code_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #5bc0de; padding: 8px 16px; border-radius: 4px; margin-left: 8px;">Code</a>' if code_url else ''
    if matched_keywords:
        kw_html = f'<div style="color:#888;font-size:13px;padding:4px 0 4px 0"><strong>关键词命中：</strong>{', '.join(matched_keywords)}</div>'
    else:
        kw_html = ''
    block_template = f"""
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
    <tr>
        <td style="font-size: 20px; font-weight: bold; color: #333;">
            {title}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #666; padding: 8px 0;">
            {authors}
            <br>
            <i>{affiliations}</i>
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>Category:</strong> {category}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>Relevance:</strong> {rate}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>arXiv ID:</strong> {arxiv_id}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>TLDR:</strong> {abstract}
        </td>
    </tr>
    <tr>
        <td>{kw_html}</td>
    </tr>
    <tr>
        <td style="padding: 8px 0;">
            <a href="{pdf_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #d9534f; padding: 8px 16px; border-radius: 4px;">PDF</a>
            {code}
        </td>
    </tr>
</table>
"""
    return block_template

def get_stars(score:float):
    full_star = '<span class="full-star">⭐</span>'
    half_star = '<span class="half-star">⭐</span>'
    low = 6
    high = 8
    if score <= low:
        return ''
    elif score >= high:
        return full_star * 5
    else:
        interval = (high-low) / 10
        star_num = math.ceil((score-low) / interval)
        full_star_num = int(star_num/2)
        half_star_num = star_num - full_star_num * 2
        return '<div class="star-wrapper">'+full_star * full_star_num + half_star * half_star_num + '</div>'


def render_email(papers:list[ArxivPaper]):
    if len(papers) == 0 :
        return framework.replace('__CONTENT__', get_empty_html())
    # 统计所有关键词
    keyword2papers = defaultdict(list)
    for p in papers:
        for kw in p.matched_keywords:
            keyword2papers[kw].append(p)
    # 按关键词分组，每组内按score降序
    group_htmls = []
    for kw, group in sorted(keyword2papers.items(), key=lambda x: x[0].lower()):
        group = sorted(group, key=lambda p: p.score if p.score is not None else 0, reverse=True)
        group_parts = []
        for p in group:
            rate = get_stars(p.score)
            authors = [a.name for a in p.authors[:5]]
            authors = ', '.join(authors)
            if len(p.authors) > 5:
                authors += ', ...'
            if p.affiliations is not None:
                affiliations = p.affiliations[:5]
                affiliations = ', '.join(affiliations)
                if len(p.affiliations) > 5:
                    affiliations += ', ...'
            else:
                affiliations = 'Unknown Affiliation'
            group_parts.append(get_block_html(
                p.title, authors, rate, p.arxiv_id, p.tldr, p.pdf_url, p.code_url, affiliations, p.category, matched_keywords=p.matched_keywords
            ))
        group_html = f'<h2 style="color:#2a7ae2">关键词：{kw}</h2>' + '<br>'.join(group_parts)
        group_htmls.append(group_html)
    content = '<br>'.join(group_htmls)
    return framework.replace('__CONTENT__', content)

def send_email(sender:str, receiver:str, password:str,smtp_server:str,smtp_port:int, html:str,):
    def _format_addr(s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    if isinstance(receiver, str):
        receivers = [r.strip() for r in receiver.split(',') if r.strip()]
    else:
        receivers = receiver

    msg = MIMEText(html, 'html', 'utf-8')
    msg['From'] = _format_addr('Github Action <%s>' % sender)
    msg['To'] = ', '.join([_format_addr('You <%s>' % r) for r in receivers])
    today = datetime.datetime.now().strftime('%Y/%m/%d')
    msg['Subject'] = Header(f'Daily arXiv {today}', 'utf-8').encode()

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
    except Exception as e:
        logger.warning(f"Failed to use TLS. {e}")
        logger.warning(f"Try to use SSL.")
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)

    server.login(sender, password)
    server.sendmail(sender, receivers, msg.as_string())
    server.quit()
