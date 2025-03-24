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

# Get Discord token and channel ID from environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_IDS = [int(channel_id.strip()) for channel_id in os.getenv('CHANNEL_IDS', '').split(',') if channel_id.strip()]

# Debug: Print environment variables (without sensitive data)
print(f"Discord Token loaded: {'Yes' if DISCORD_TOKEN else 'No'}")
print(f"Channel IDs loaded: {'Yes' if CHANNEL_IDS else 'No'}")
print(f"RapidAPI Key loaded: {'Yes' if os.getenv('RAPIDAPI_KEY') else 'No'}")

# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
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

@tasks.loop(minutes=30)
async def check_internships():
    """Check for new internships every 30 minutes"""
    try:
        print("Fetching internship data...")
        internships = fetch_internships()
        
        if internships:
            print(f"Found {len(internships)} internships")
            embeds = format_internship_embed(internships)
            
            # Send to all specified channels
            for channel_id in CHANNEL_IDS:
                try:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        # Send initial message
                        await channel.send(f"🔍 Found {len(embeds)} new internship opportunities!")
                        
                        # Send each embed as a separate message
                        for embed in embeds:
                            await channel.send(embed=embed)
                            await asyncio.sleep(1)  # Small delay between messages to avoid rate limits
                    else:
                        print(f"Could not find channel with ID: {channel_id}")
                except Exception as e:
                    print(f"Error sending message to channel {channel_id}: {str(e)}")
        else:
            print("No new internships found")
            
    except Exception as e:
        print(f"Error in check_internships: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord"""
    print(f"{bot.user.name} has connected to Discord!")
    
    # Start the internship checking loop
    check_internships.start()

@bot.command(name='internships')
async def get_internships(ctx):
    """Show all available internships"""
    try:
        # Check if the command is used in an allowed channel
        if ctx.channel.id not in CHANNEL_IDS:
            return
            
        # Send a loading message
        loading_msg = await ctx.send("Fetching internships...")
        
        # Fetch internships
        internships = fetch_internships()
        
        # Delete the loading message
        await loading_msg.delete()
        
        if internships:
            embeds = format_internship_embed(internships)
            
            # Send initial message
            await ctx.send(f"🔍 Found {len(embeds)} internship opportunities!")
            
            # Send each embed as a separate message
            for embed in embeds:
                await ctx.send(embed=embed)
                await asyncio.sleep(1)  # Small delay between messages to avoid rate limits
        else:
            await ctx.send("No internships found at the moment.")
            
    except Exception as e:
        await ctx.send(f"An error occurred while fetching internships: {str(e)}")
        print(f"Error in get_internships command: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

@bot.command(name='search')
async def search(ctx, *, query: str):
    """Search for internships by keyword"""
    try:
        # Check if the command is used in an allowed channel
        if ctx.channel.id not in CHANNEL_IDS:
            return
            
        # Send a loading message
        loading_msg = await ctx.send(f"Searching for internships matching '{query}'...")
        
        # Fetch and filter internships
        internships = fetch_internships()
        filtered_internships = search_internships(internships, query)
        
        # Delete the loading message
        await loading_msg.delete()
        
        if filtered_internships:
            embeds = format_internship_embed(
                filtered_internships,
                title=f"Search Results for '{query}'",
                description=f"Found {len(filtered_internships)} matching internships"
            )
            
            # Send initial message
            await ctx.send(f"🔍 Found {len(embeds)} internships matching '{query}'!")
            
            # Send each embed as a separate message
            for embed in embeds:
                await ctx.send(embed=embed)
                await asyncio.sleep(1)  # Small delay between messages to avoid rate limits
        else:
            await ctx.send(f"No internships found matching '{query}'.")
            
    except Exception as e:
        await ctx.send(f"An error occurred while searching internships: {str(e)}")
        print(f"Error in search command: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

@bot.command(name='recent')
async def recent(ctx, limit: int = 5):
    """Show the most recent internships"""
    try:
        # Check if the command is used in an allowed channel
        if ctx.channel.id not in CHANNEL_IDS:
            return
            
        # Validate limit
        limit = max(1, min(limit, 50))  # Keep limit between 1 and 50
        
        # Send a loading message
        loading_msg = await ctx.send(f"Fetching {limit} most recent internships...")
        
        # Fetch and sort internships
        internships = fetch_internships()
        sorted_internships = sorted(
            internships,
            key=lambda x: x.get('date_posted', ''),
            reverse=True
        )[:limit]
        
        # Delete the loading message
        await loading_msg.delete()
        
        if sorted_internships:
            embeds = format_internship_embed(
                sorted_internships,
                title=f"Most Recent Internships",
                description=f"Showing {len(sorted_internships)} most recent opportunities"
            )
            
            # Send initial message
            await ctx.send(f"🔍 Found {len(embeds)} recent internship opportunities!")
            
            # Send each embed as a separate message
            for embed in embeds:
                await ctx.send(embed=embed)
                await asyncio.sleep(1)  # Small delay between messages to avoid rate limits
        else:
            await ctx.send("No recent internships found.")
            
    except Exception as e:
        await ctx.send(f"An error occurred while fetching recent internships: {str(e)}")
        print(f"Error in recent command: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

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
        # Check if the command is used in an allowed channel
        if ctx.channel.id not in CHANNEL_IDS:
            return
            
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
    if DISCORD_TOKEN and CHANNEL_IDS:
        print("Starting bot...")
        bot.run(DISCORD_TOKEN)
    else:
        if not DISCORD_TOKEN:
            print("Please provide your Discord token in the .env file.")
        if not CHANNEL_IDS:
            print("Please provide your channel IDs in the .env file.") 