# scraper_async.py
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
import pandas as pd
from urllib.parse import urljoin, urlparse
from typing import Set, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AsyncEmailScraper:
    def __init__(self, max_concurrent=1000, timeout=5):
        """
        max_concurrent: Number of simultaneous requests (200-500 recommended)
        timeout: Request timeout in seconds
        """
        self.emails = set()
        self.visited_urls = set()
        self.scraped_domains = {}
        self.max_concurrent = max_concurrent
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        
        self.blocked_domains = [
            'estatesales.net', 'estatesales.org', 'godaddy.com',
            'hibid.com', 'bluemoonestatesales.com', 'galleryauctions.com',
            'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com'
        ]
        
        self.MAX_URLS_PER_DOMAIN = 15
        self.unwanted_patterns = [
            'wix', 'example', 'domain', 'sentry',
            'webp', 'jpg', 'png', 'gif', 'svg'
        ]
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def is_blocked_domain(self, url: str) -> bool:
        """Check if URL belongs to blocked domains"""
        if pd.isna(url) or not url or not isinstance(url, str):
            return False
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower().replace('www.', '')
            return any(blocked in domain for blocked in self.blocked_domains)
        except Exception:
            return False
    
    def get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower().replace('www.', '')
        except:
            return ""
    
    def is_valid_email(self, email: str) -> bool:
        """Validate email format and filter unwanted ones"""
        email = email.lower()
        
        # Basic email pattern
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return False
        
        # Filter unwanted patterns
        for pattern in self.unwanted_patterns:
            if pattern in email:
                return False
        
        # Filter common invalid emails
        invalid_patterns = [
            'example', 'test', 'admin@admin', 'noreply',
            'no-reply', 'webmaster', 'postmaster'
        ]
        
        for pattern in invalid_patterns:
            if pattern in email:
                return False
        
        return True
    
    def extract_emails_from_text(self, text: str) -> Set[str]:
        """Extract valid emails from text"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = set(re.findall(email_pattern, text))
        return {email for email in emails if self.is_valid_email(email)}
    
    async def fetch_url(self, session: aiohttp.ClientSession, url: str) -> tuple:
        """Fetch single URL asynchronously"""
        try:
            # Normalize URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            async with session.get(url, headers=self.headers, ssl=False) as response:
                if response.status == 200:
                    text = await response.text()
                    return url, text, None
                else:
                    return url, None, f"HTTP {response.status}"
        except asyncio.TimeoutError:
            return url, None, "Timeout"
        except Exception as e:
            return url, None, str(e)[:50]
    
    async def scrape_single_page(self, session: aiohttp.ClientSession, url: str, base_url: str, max_depth: int = 2) -> Set[str]:
        """Scrape a single page and find links"""
        if url in self.visited_urls:
            return set()
        
        self.visited_urls.add(url)
        domain = self.get_domain(url)
        
        # Check domain limit
        if domain in self.scraped_domains:
            if self.scraped_domains[domain] >= self.MAX_URLS_PER_DOMAIN:
                return set()
            self.scraped_domains[domain] += 1
        else:
            self.scraped_domains[domain] = 1
        
        url_result, html, error = await self.fetch_url(session, url)
        
        if html:
            # Extract emails
            emails = self.extract_emails_from_text(html)
            self.emails.update(emails)
            
            # Find links for deeper scraping
            if max_depth > 0:
                soup = BeautifulSoup(html, 'html.parser')
                links = set()
                
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    full_url = urljoin(base_url, href)
                    
                    # Only follow internal links
                    if self.get_domain(full_url) == self.get_domain(base_url):
                        if full_url not in self.visited_urls:
                            links.add(full_url)
                
                return links
        
        return set()
    
    async def scrape_website(self, url: str, max_depth: int = 2) -> Set[str]:
        """Scrape website with depth-first approach"""
        if not url or pd.isna(url):
            return set()
        
        if self.is_blocked_domain(url):
            return set()
        
        # Normalize URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        base_url = url
        self.emails = set()
        self.visited_urls = set()
        self.scraped_domains = {}
        
        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False)
        
        async with aiohttp.ClientSession(connector=connector, timeout=self.timeout) as session:
            current_depth_urls = {url}
            
            for depth in range(max_depth + 1):
                if not current_depth_urls:
                    break
                
                # Create tasks for all URLs at current depth
                tasks = [
                    self.scrape_single_page(session, page_url, base_url, max_depth - depth)
                    for page_url in current_depth_urls
                    if page_url not in self.visited_urls
                ]
                
                if not tasks:
                    break
                
                # Execute all tasks concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Collect URLs for next depth
                next_depth_urls = set()
                for result in results:
                    if isinstance(result, set):
                        next_depth_urls.update(result)
                
                current_depth_urls = next_depth_urls
        
        return self.emails


def format_phone_number(phone):
    """Format phone number"""
    if pd.isna(phone):
        return ""
    cleaned = str(phone)
    cleaned = re.sub(r'[\(\)\-\s\.]', '', cleaned)
    cleaned = cleaned.replace('+1', '')
    cleaned = re.sub(r'^[^\d]+|[^\d]+$', '', cleaned)
    if len(cleaned) == 10 and cleaned.isdigit():
        return f"+1{cleaned}"
    return cleaned


async def scrape_multiple_websites(websites_data: List[dict], max_concurrent: int = 200) -> List[dict]:
    """
    Scrape multiple websites concurrently - each gets its own scraper instance
    """
    results = []
    
    # Semaphore to control concurrency
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def scrape_one(data):
        async with semaphore:  # Limit concurrent operations
            website = data['website']
            company = data['company']
            phone = data.get('phone', '')
            city = data.get('city', '')
            formatted_phone = format_phone_number(phone)
            
            if pd.isna(website) or not website or not isinstance(website, str):
                return {
                    'Company': company,
                    'Website': 'No website',
                    'Phone Number': formatted_phone,
                    'Email': 'No website provided',
                    'City': city
                }
            
            # CREATE FRESH SCRAPER FOR THIS WEBSITE ONLY
            scraper = AsyncEmailScraper(max_concurrent=50)  # Lower concurrency per site
            
            if scraper.is_blocked_domain(website):
                return {
                    'Company': company,
                    'Website': website,
                    'Phone Number': formatted_phone,
                    'Email': 'Blocked domain',
                    'City': city
                }
            
            try:
                emails = await scraper.scrape_website(website, max_depth=2)
                
                if emails:
                    return [
                        {
                            'Company': company,
                            'Website': website,
                            'Phone Number': formatted_phone,
                            'Email': email,
                            'City': city
                        }
                        for email in emails
                    ]
                else:
                    return {
                        'Company': company,
                        'Website': website,
                        'Phone Number': formatted_phone,
                        'Email': 'No email found',
                        'City': city
                    }
            except Exception as e:
                return {
                    'Company': company,
                    'Website': website,
                    'Phone Number': formatted_phone,
                    'Email': f'Error: {str(e)[:50]}',
                    'City': city
                }
    
    # Create tasks for all websites
    tasks = [scrape_one(data) for data in websites_data]
    
    # Execute all concurrently
    completed_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Flatten results
    for result in completed_results:
        if isinstance(result, list):
            results.extend(result)
        elif isinstance(result, dict):
            results.append(result)
        elif isinstance(result, Exception):
            logger.error(f"Error in scraping: {result}")
    
    return results
