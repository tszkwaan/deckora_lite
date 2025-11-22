"""
Example usage of Open Peeps search system.

This demonstrates how to use the search functionality both via API and directly.
"""

# Example 1: Direct search (without API server)
from presentation_agent.assets.peeps.search_utils import search_peeps_local, get_peeps_image_url

print("=" * 60)
print("Example 1: Direct Search")
print("=" * 60)

# Search for illustrations
results = search_peeps_local("security", limit=3)
print(f"\nSearch results for 'security':")
for i, result in enumerate(results, 1):
    print(f"  {i}. {result['name']} (score: {result['score']})")
    print(f"     URL: {result['url']}")

# Get best match
print("\n" + "=" * 60)
print("Example 2: Get Best Match")
print("=" * 60)
image_url = get_peeps_image_url("warning")
print(f"Best match for 'warning': {image_url}")

# Example 3: Via API (if server is running)
print("\n" + "=" * 60)
print("Example 3: Via API (if server running)")
print("=" * 60)
try:
    import requests
    response = requests.get("http://localhost:8000/api/peeps/search", params={"query": "analytics", "limit": 3})
    if response.status_code == 200:
        data = response.json()
        print(f"Query: {data['query']}")
        print(f"Results: {data['total_found']}")
        for result in data['results']:
            print(f"  - {result['name']} (score: {result['score']})")
    else:
        print("API server not running. Start with: python search_api.py")
except Exception as e:
    print(f"API server not available: {e}")
    print("Start server with: python search_api.py")

