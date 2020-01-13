import tweepy
import logging
import os

logger = logging.getLogger()

def create_api():
    consumer_key = os.environ.get("twitter_soccer_consumer_key")
    consumer_secret = os.environ.get("twitter_soccer_consumer_key_s")
    access_token = os.environ.get("twitter_soccer_access_token")
    access_secret = os.environ.get("twitter_soccer_access_s")
    
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_secret)
    api = tweepy.API(auth, wait_on_rate_limit=True, 
        wait_on_rate_limit_notify=True)
    try:
        api.verify_credentials()
    except Exception as e:
        logger.error("Error creating API", exc_info=True)
        raise e
    logger.info("API created")
    return api