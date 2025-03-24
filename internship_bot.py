import os
import discord
from discord.ext import commands, tasks
import requests
from ratelimit import limits, sleep_and_retry
from dotenv import load_dotenv
import asyncio
from datetime import datetime

# Load environment variables
load_dotenv()

# Debug: Print environment variables
discord_token = os.getenv('DISCORD_TOKEN')
channel_id = os.getenv('CHANNEL_ID')
rapidapi_key = os.getenv('RAPIDAPI_KEY')
print(f"Discord Token loaded: {'Yes' if discord_token else 'No'}")
print(f"Channel ID loaded: {'Yes' if channel_id else 'No'}")
print(f"RapidAPI Key loaded: {'Yes' if rapidapi_key else 'No'}")

# Initialize Discord bot and global variables
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Rate limiting configuration
CALLS_PER_MINUTE = 30
ONE_MINUTE = 60

@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=ONE_MINUTE)
def fetch_internships():
    """Fetch internships from multiple endpoints"""
    all_internships = []
    
    # RapidAPI endpoints for internships
    internship_endpoints = [
        "https://internships-api.p.rapidapi.com/active-ats-7d",  # Last 7 days
        "https://internships-api.p.rapidapi.com/active-ats-30d",  # Last 30 days
        "https://internships-api.p.rapidapi.com/active-ats-90d"   # Last 90 days
    ]
    
    # LinkedIn API endpoint
    linkedin_url = "https://linkedin-job-search-api.p.rapidapi.com/active-jb-1h"
    
    headers = {
        "x-rapidapi-key": os.getenv('RAPIDAPI_KEY'),
        "x-rapidapi-host": "internships-api.p.rapidapi.com"
    }
    
    linkedin_headers = {
        "x-rapidapi-key": os.getenv('RAPIDAPI_KEY'),
        "x-rapidapi-host": "linkedin-job-search-api.p.rapidapi.com"
    }
    
    # Fetch from internship endpoints
    for endpoint in internship_endpoints:
        try:
            response = requests.get(endpoint, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    # Add source information
                    for job in data:
                        job['source'] = 'Internship API'
                    all_internships.extend(data)
                    print(f"Debug - Fetched {len(data)} internships from {endpoint}")
        except Exception as e:
            print(f"Error fetching from {endpoint}: {e}")
            continue
    
    # Fetch from LinkedIn API
    try:
        querystring = {
            "offset": "0",
            "title_filter": "\"Intern\" OR \"Internship\"",
            "location_filter": "\"United States\" OR \"United Kingdom\""
        }
        response = requests.get(linkedin_url, headers=linkedin_headers, params=querystring)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                # Transform LinkedIn data to match our format
                for job in data:
                    transformed_job = {
                        'title': job.get('title', ''),
                        'companyName': job.get('company_name', ''),
                        'location': job.get('location', ''),
                        'url': job.get('apply_url', ''),
                        'postedDate': job.get('posted_date', ''),
                        'source': 'LinkedIn',
                        'description': job.get('description', '')[:200] + '...' if job.get('description') else None
                    }
                    all_internships.append(transformed_job)
                print(f"Debug - Fetched {len(data)} jobs from LinkedIn API")
    except Exception as e:
        print(f"Error fetching from LinkedIn API: {e}")
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_internships = []
    for internship in all_internships:
        url = internship.get('url')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_internships.append(internship)
    
    # Sort by posting date (most recent first)
    unique_internships.sort(key=lambda x: x.get('postedDate', x.get('posted_date', '')), reverse=True)
    
    print(f"Debug - Total unique internships found: {len(unique_internships)}")
    return unique_internships

def format_internship_embed(data, title="Latest Internship Opportunities", description="Here are the most recent internship postings:", limit=25):
    """Format internship data into individual Discord embeds"""
    embeds = []
    
    # Create individual embed for each internship
    for internship in data[:limit]:
        # Print the internship data for debugging
        print(f"Debug - Raw internship data: {internship}")
        
        # Extract data with proper fallbacks
        job_title = internship.get('title', 'No Title')
        company_name = internship.get('companyName', internship.get('company_name', internship.get('company', 'Unknown Company')))
        location = internship.get('locations', [internship.get('location', 'Location not specified')])[0]
        posted_date = internship.get('postedDate', internship.get('posted_date', 'Date not specified'))
        source = internship.get('source', 'Unknown Source')
        description = internship.get('description', '')[:200] + '...' if internship.get('description') else None
        
        # Only create embed if we have at least a title or company name
        if job_title != 'No Title' or company_name != 'Unknown Company':
            embed = discord.Embed(
                title=f"{company_name} - {job_title}",
                description=f"🏢 {company_name}\n💼 {job_title}",
                color=discord.Color.blue(),
                url=internship.get('url', None)
            )
            
            embed.add_field(name="📍 Location", value=location, inline=True)
            embed.add_field(name="📅 Posted", value=posted_date, inline=True)
            embed.add_field(name="🔍 Source", value=source, inline=True)
            
            if description:
                embed.add_field(name="📝 Description", value=description, inline=False)
            
            if internship.get('sponsorship'):
                embed.add_field(name="🌐 Sponsorship", value=internship['sponsorship'], inline=True)
                
            if internship.get('season'):
                embed.add_field(name="🗓️ Season", value=internship['season'], inline=True)
                
            # Add footer with current time
            embed.set_footer(text=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            embeds.append(embed)
        else:
            print("Debug - Skipping embed creation due to missing required data")
    
    return embeds

def search_internships(data, query):
    """Search internships by query (matches against company, title, and location)"""
    query = query.lower()
    matches = []
    
    for internship in data:
        # Search in company name (try all possible fields)
        company = internship.get('companyName', 
                               internship.get('company_name',
                                            internship.get('company', '')))
        if query in company.lower():
            matches.append(internship)
            continue
            
        # Search in title
        if query in internship.get('title', '').lower():
            matches.append(internship)
            continue
            
        # Search in location
        if query in internship.get('location', '').lower():
            matches.append(internship)
            continue
            
        # Search in locations list if it exists
        if isinstance(internship.get('locations'), list):
            if any(query in loc.lower() for loc in internship['locations']):
                matches.append(internship)
                continue
    
    # Sort matches by posting date (most recent first)
    matches.sort(key=lambda x: x.get('postedDate', x.get('posted_date', '')), reverse=True)
    return matches

@tasks.loop(minutes=30)  # Check for new internships every 30 minutes
async def check_internships():
    """Periodically check for new internships and post them"""
    if not channel_id:
        print("No channel ID configured!")
        return
        
    try:
        channel = bot.get_channel(int(channel_id))
        if not channel:
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except discord.NotFound:
                print(f"Could not find channel with ID {channel_id}")
                return
            except discord.Forbidden:
                print(f"No permission for channel {channel_id}")
                return
            except Exception as e:
                print(f"Error fetching channel {channel_id}: {e}")
                return
            
        # Fetch the data with rate limiting
        print("Fetching internship data...")
        data = fetch_internships()
        
        if isinstance(data, list) and len(data) > 0:
            # Sort by posting date to show most recent first
            sorted_data = sorted(data, key=lambda x: x.get('posted_date', ''), reverse=True)
            embeds = format_internship_embed(sorted_data)
            
            # Send initial message
            await channel.send(f"📢 Found {len(embeds)} new internship opportunities!")
            
            # Send each embed as a separate message
            for embed in embeds:
                await channel.send(embed=embed)
                await asyncio.sleep(1)  # Small delay between messages to avoid rate limits
                
            print(f"Successfully sent internship updates to channel {channel_id}")
        else:
            print("No internship opportunities found at the moment.")
            
    except Exception as e:
        print(f"An error occurred while checking internships: {e}")

@bot.event
async def on_ready():
    """When the bot is ready, start the internship checking loop"""
    print(f'{bot.user} has connected to Discord!')
    if not check_internships.is_running():
        check_internships.start()

@bot.command(name='internships')
async def get_internships(ctx, limit: int = 25):
    """
    Manual command to fetch internships
    Usage: !internships [number]
    Example: !internships 30
    """
    try:
        # Validate limit
        limit = max(1, min(limit, 50))  # Keep limit between 1 and 50
        
        # Send a loading message
        loading_msg = await ctx.send(f"Fetching {limit} internship opportunities...")
        
        # Fetch the data with rate limiting
        data = fetch_internships()
        
        # Delete the loading message
        await loading_msg.delete()
        
        if isinstance(data, list) and len(data) > 0:
            embeds = format_internship_embed(data, limit=limit)
            
            # Send initial message
            await ctx.send(f"📢 Found {len(embeds)} internship opportunities!")
            
            # Send each embed as a separate message
            for embed in embeds:
                await ctx.send(embed=embed)
                await asyncio.sleep(1)  # Small delay between messages to avoid rate limits
        else:
            await ctx.send("No internship opportunities found at the moment.")
            
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

@bot.command(name='search')
async def search(ctx, *, query: str, limit: int = 25):
    """
    Search for internships by company name, title, or location
    Usage: !search <query> [number]
    Example: !search google 30
    Example: !search software engineer 20
    Example: !search remote 15
    """
    try:
        # Extract limit if provided at the end of the query
        parts = query.split()
        if parts[-1].isdigit():
            limit = int(parts[-1])
            query = ' '.join(parts[:-1])
        
        # Validate limit
        limit = max(1, min(limit, 50))  # Keep limit between 1 and 50
        
        # Send a loading message
        loading_msg = await ctx.send(f"Searching internships for '{query}' (up to {limit} results)...")
        
        # Fetch the data with rate limiting
        data = fetch_internships()
        
        # Delete the loading message
        await loading_msg.delete()
        
        if isinstance(data, list) and len(data) > 0:
            # Search for matching internships
            matches = search_internships(data, query)
            
            if matches:
                embeds = format_internship_embed(
                    matches,
                    title=f"Search Results for '{query}'",
                    description=f"Found {len(matches)} matching internships (showing most recent first):",
                    limit=limit
                )
                
                # Send initial message
                await ctx.send(f"🔍 Found {len(embeds)} internships matching '{query}'!")
                
                # Send each embed as a separate message
                for embed in embeds:
                    await ctx.send(embed=embed)
                    await asyncio.sleep(1)  # Small delay between messages to avoid rate limits
            else:
                await ctx.send(f"No internships found matching '{query}'.")
        else:
            await ctx.send("No internship opportunities found at the moment.")
            
    except Exception as e:
        await ctx.send(f"An error occurred while searching: {str(e)}")

@bot.command(name='recent')
async def recent(ctx, limit: int = 25):
    """
    Show the most recently posted internships
    Usage: !recent [number]
    Example: !recent 30
    """
    try:
        # Validate limit
        limit = max(1, min(limit, 50))  # Keep limit between 1 and 50
        
        # Send a loading message
        loading_msg = await ctx.send(f"Fetching {limit} recent internships...")
        
        # Fetch the data with rate limiting
        data = fetch_internships()
        
        # Delete the loading message
        await loading_msg.delete()
        
        if isinstance(data, list) and len(data) > 0:
            # Sort by posting date
            sorted_data = sorted(data, key=lambda x: x.get('posted_date', ''), reverse=True)
            # Apply the limit
            sorted_data = sorted_data[:limit]
            
            embeds = format_internship_embed(
                sorted_data,
                title=f"{limit} Most Recent Internships",
                description="Here are the latest internship postings:",
                limit=limit
            )
            
            # Send initial message
            await ctx.send(f"📅 Here are the {len(embeds)} most recent internship postings!")
            
            # Send each embed as a separate message
            for embed in embeds:
                await ctx.send(embed=embed)
                await asyncio.sleep(1)  # Small delay between messages to avoid rate limits
        else:
            await ctx.send("No internship opportunities found at the moment.")
            
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=ONE_MINUTE)
def fetch_linkedin_jobs(keywords=None, location=None, limit=25, time_range="past24h"):
    """Fetch jobs specifically from LinkedIn API"""
    if not os.getenv('RAPIDAPI_KEY'):
        print("Error: RapidAPI key not found in environment variables")
        return []
        
    linkedin_url = "https://linkedin-data-api.p.rapidapi.com/search-jobs-v2"
    
    headers = {
        "x-rapidapi-key": os.getenv('RAPIDAPI_KEY'),
        "x-rapidapi-host": "linkedin-data-api.p.rapidapi.com"
    }
    
    # Debug: Print headers (without the API key)
    print(f"Debug - LinkedIn API Headers: {dict(headers, x_rapidapi_key='[REDACTED]')}")
    
    # Build querystring with filters
    querystring = {
        "keywords": keywords or "internship",
        "locationId": "92000000",  # United States
        "datePosted": time_range,  # Use time_range parameter
        "sort": "mostRecent"  # Sort by most recent
    }
    
    # Add location to keywords if specified
    if location:
        querystring["keywords"] = f"{keywords or 'internship'} {location}"
    
    # Debug: Print querystring
    print(f"Debug - LinkedIn API Querystring: {querystring}")
    
    try:
        print(f"Debug - Making request to LinkedIn API...")
        response = requests.get(linkedin_url, headers=headers, params=querystring)
        
        # Debug: Print response status and headers
        print(f"Debug - LinkedIn API Response Status: {response.status_code}")
        print(f"Debug - LinkedIn API Response Headers: {dict(response.headers)}")
        print(f"Debug - LinkedIn API Response Text: {response.text[:500]}")  # Print first 500 chars of response
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Debug - LinkedIn API Response Data Type: {type(data)}")
                
                # Transform LinkedIn data to match our format
                jobs = []
                if isinstance(data, dict):
                    # Get the jobs array from the response
                    jobs_data = data.get('data', [])
                    print(f"Debug - Found {len(jobs_data)} jobs in response")
                    
                    for job in jobs_data[:limit]:
                        # Get company info from the nested company object
                        company = job.get('company', {})
                        transformed_job = {
                            'title': job.get('title', ''),
                            'companyName': company.get('name', ''),
                            'location': job.get('location', ''),
                            'url': job.get('url', ''),
                            'postedDate': job.get('postAt', ''),
                            'source': 'LinkedIn',
                            'description': job.get('description', '')
                        }
                        
                        # Only add the job if we have at least a title or company name
                        if transformed_job['title'] or transformed_job['companyName']:
                            jobs.append(transformed_job)
                            print(f"Debug - Transformed job data: {transformed_job}")
                        else:
                            print("Debug - Skipping job due to missing required data")
                else:
                    print(f"Debug - LinkedIn API Response is not a dictionary: {data}")
            except ValueError as e:
                print(f"Debug - Error parsing JSON response: {e}")
                print(f"Debug - Raw response text: {response.text}")
        else:
            print(f"Debug - LinkedIn API Error Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"Debug - Request error: {str(e)}")
        print(f"Debug - Error type: {type(e)}")
        import traceback
        print(f"Debug - Full traceback: {traceback.format_exc()}")
    except Exception as e:
        print(f"Debug - Unexpected error: {str(e)}")
        print(f"Debug - Error type: {type(e)}")
        import traceback
        print(f"Debug - Full traceback: {traceback.format_exc()}")
    
    return jobs

@bot.command(name='linkedin')
async def linkedin_jobs(ctx, *, query: str = None):
    """
    Show LinkedIn job postings
    Usage: !linkedin [keywords] [location] [limit] [time_range]
    Examples:
    !linkedin
    !linkedin "software engineer" "boston" 20
    !linkedin "data scientist" "new york" 30
    !linkedin "developer" "past24h"
    """
    try:
        # Check if RapidAPI key is available
        if not os.getenv('RAPIDAPI_KEY'):
            await ctx.send("Error: RapidAPI key not found. Please check your .env file.")
            return
            
        # Parse the query string
        keywords = None
        location = None
        limit = 25
        time_range = "past24h"  # Default to last 24 hours
        
        if query:
            parts = query.split()
            # Check if last part is a number (limit)
            if parts[-1].isdigit():
                limit = int(parts[-1])
                parts = parts[:-1]
            
            # Check for time range keywords
            time_keywords = {
                "past24h": ["24h", "24hours", "today", "past24h"],
                "past72h": ["72h", "72hours", "3days", "past72h"],
                "pastWeek": ["week", "7days", "pastweek"],
                "pastMonth": ["month", "30days", "pastmonth"],
                "anyTime": ["any", "all", "anytime"]
            }
            
            for time_key, keywords_list in time_keywords.items():
                if parts[-1].lower() in keywords_list:
                    time_range = time_key
                    parts = parts[:-1]
                    break
            
            # If we have remaining parts, try to identify location
            if len(parts) >= 2:
                # Common location indicators
                location_indicators = ['in', 'at', 'near', 'around', 'within']
                for i, part in enumerate(parts):
                    if part.lower() in location_indicators and i + 1 < len(parts):
                        location = ' '.join(parts[i+1:])
                        keywords = ' '.join(parts[:i])
                        break
                
                # If no location indicator found, assume last part is location
                if not location:
                    location = parts[-1]
                    keywords = ' '.join(parts[:-1])
            else:
                keywords = ' '.join(parts)
        
        # Validate limit
        limit = max(1, min(limit, 50))  # Keep limit between 1 and 50
        
        # Send a loading message
        search_query = f"Searching LinkedIn jobs for '{keywords or 'internship'}'"
        if location:
            search_query += f" in {location}"
        if time_range != "anyTime":
            search_query += f" posted in the last {time_range}"
        await ctx.send(f"{search_query}...")
        
        # Fetch LinkedIn jobs
        jobs = fetch_linkedin_jobs(keywords=keywords, location=location, limit=limit, time_range=time_range)
        
        if jobs:
            embeds = format_internship_embed(
                jobs,
                title="LinkedIn Job Postings",
                description=f"Found {len(jobs)} jobs" + 
                          (f" matching '{keywords}'" if keywords else "") +
                          (f" in {location}" if location else "") +
                          (f" posted in the last {time_range}" if time_range != "anyTime" else ""),
                limit=limit
            )
            
            # Send initial message
            await ctx.send(f"🔍 Found {len(embeds)} LinkedIn jobs!")
            
            # Send each embed as a separate message
            for embed in embeds:
                await ctx.send(embed=embed)
                await asyncio.sleep(1)  # Small delay between messages to avoid rate limits
        else:
            await ctx.send("No jobs found at the moment. Please try different keywords, location, or time range.")
            
    except Exception as e:
        await ctx.send(f"An error occurred while fetching LinkedIn jobs: {str(e)}")
        print(f"Error in linkedin_jobs command: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

# Run the bot
if __name__ == "__main__":
    if discord_token and channel_id:
        print("Starting bot...")
        bot.run(discord_token)
    else:
        if not discord_token:
            print("Please provide your Discord token in the .env file.")
        if not channel_id:
            print("Please provide your channel ID in the .env file.") 