import json
import requests
import feedparser
from bs4 import BeautifulSoup
import openai
from datetime import datetime, timedelta
import time
import os
from requests_oauthlib import OAuth1Session


# VARIABLES
openai.api_key = os.environ.get('openai_key', 'Default Value') # OPENAI
x_access_token = os.environ.get('x_access_token', 'Default Value') # X / Twitter
x_access_token_secret = os.environ.get('x_access_token_secret', 'Default Value') # X / Twitter
x_consumer_key = os.environ.get('x_consumer_key', 'Default Value') # X / Twitter
x_consumer_secret = os.environ.get('x_consumer_secret', 'Default Value') # X / Twitter

time_period=3 # max age in hours of articles to select

keywords_tech = [
    'generative ai',
    'genai',
    'llm',
    'chatgpt',
    'gpt4',
    'inflection',
    'adept',
    'anthropic',
    'cohere',
    'bard',
    'hugging face',
    'Nvidia',
    'Github Copilot'
]

rss_feed_urls = [
    'https://www.infoworld.com/uk/index.rss',
    'https://www.wired.com/feed/rss',
    'https://www.forbes.com/innovation/feed2',
    'http://feeds.feedburner.com/venturebeat/SZYF',
    'https://mashable.com/feeds/rss/all',
    'https://www.cnbc.com/id/100727362/device/rss/rss.html',
    'https://techcrunch.com/feed/',
    'https://dailyai.com/feed/',
    'https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml',
    'https://analyticsindiamag.com/feed/',
    'https://www.cnet.com/rss/news/',
    'https://www.zdnet.com/news/rss.xml'
    # Add more feed URLs here
]

# FUNCTIONS

print('Loading function')

# Post to X / Twitter
def x_post(post_summary):
    from requests_oauthlib import OAuth1Session

    # Be sure to add replace the text of the with the text you wish to Tweet. You can also add parameters to post polls, quote Tweets, Tweet with reply settings, and Tweet to Super Followers in addition to other features.
    payload = {"text": post_summary}
    
    # Get request token
    request_token_url = "https://api.twitter.com/oauth/request_token?oauth_callback=oob&x_auth_access_type=write"
    oauth = OAuth1Session(x_consumer_key, client_secret=x_consumer_secret)
    
    try:
        fetch_response = oauth.fetch_request_token(request_token_url)
    except ValueError:
        print(
            "There may have been an issue with the consumer_key or consumer_secret you entered."
        )
    
    
    # Make the request
    oauth = OAuth1Session(
        x_consumer_key,
        client_secret=x_consumer_secret,
        resource_owner_key=x_access_token,
        resource_owner_secret=x_access_token_secret,
    )
    
    # Making the request
    response = oauth.post(
        "https://api.twitter.com/2/tweets",
        json=payload,
    )
    
    if response.status_code != 201:
        raise Exception(
            "Request returned an error: {} {}".format(response.status_code, response.text)
        )
    
    print("Response code: {}".format(response.status_code))
    
    # Saving the response as JSON
    json_response = response.json()
    print(json.dumps(json_response, indent=4, sort_keys=True))


# Handle date formats from different RSS feeds
def parse_date(published_date_str):
    # Manual conversion of some known timezones to their UTC offsets.
    timezone_mappings = {
        'EDT': '-0400',
        'EST': '-0500',
        'CST': '-0600',
        'PST': '-0800'
        # Add more mappings as needed
    }
    
    for tz, offset in timezone_mappings.items():
        published_date_str = published_date_str.replace(tz, offset)

    formats = ["%a, %d %b %Y %H:%M:%S %z","%a, %d %b %Y %H:%M:%S %Z"]
    
    for fmt in formats:
        try:
            return datetime.strptime(published_date_str, fmt)
        except ValueError:
            continue

    return None

#Check if article is too old
def is_old(published_date_str):
    published_date = parse_date(published_date_str)
                    
    if published_date is not None:
        # Get the current time and date
        current_date = datetime.now(published_date.tzinfo)
        # Calculate the time difference
        time_difference = current_date - published_date
        # Check if it's more than 24 hours old
        if time_difference < timedelta(hours=time_period):
            return False
        else:
            return True


# Scrape the article for gpt 
def scrape_article_text(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    article_body = soup.find("article")
    if article_body is None:
        return None
    article_text = article_body.get_text(separator="\n")
    return article_text.strip()

# Comes up with an alternate text for the post instead of just using the RSS headline. If we can scrape the article and it's not too long, we send the whole article to GPT. Otherwise we send the ecisting title
def ai_alt_title(article_in, title_in):
    text_for_opeanai = scrape_article_text(article_in)
    if text_for_opeanai is None: # If scraping failed, just use the title
        text_for_opeanai = title_in
    if len(text_for_opeanai) > 15000: #This is too long for GPT to handle
        text_for_opeanai = title_in
    response = openai.ChatCompletion.create(
#        model="gpt-3.5-turbo",
        model="gpt-4", # More reliable
        messages=[
            {"role": "system", "content": "You will be provided with a news article, and your task is to create a single sentence summary to post to Twitter. Please add relevant hastags after the headline.The whole text must be less than 280 characters."},
            {"role": "user", "content": text_for_opeanai}
        ],
        temperature=0,
        max_tokens=250,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0
    )
    return response.choices[0].message['content'].strip()

# Process the RSS feeds searching for a relevant article
def search_feeds(feed_urls, first_list=None):   
    counter = 0
    the_post = ""
    for feed_url in feed_urls:
        feed = feedparser.parse(feed_url)
                    
        if feed.status == 200:
            for entry in feed.entries:
                if hasattr(entry,'published'):
                    if not is_old(entry.published):
                        if any(item.lower() in entry.title.lower() for item in first_list):
                            counter += 1
                            if counter == 1:                    
                                new_title = ai_alt_title(entry.link, entry.title)
                                if len(new_title) < 20:
                                    new_title = entry.title
                                the_post = new_title + "\n" + entry.link + "\n\n"
        
    print("End")
    return the_post, counter


def lambda_handler(event, context):
    storycount = 0
    my_summary, storycount = search_feeds(rss_feed_urls, keywords_tech)
    print("_" * 20)
    print("Count: ", storycount)
    if storycount > 0:
        x_post(my_summary)
    else:
        print("no stories")
    return	


