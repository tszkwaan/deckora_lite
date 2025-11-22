"""
Quick test script to search for "computer" and see results.
"""

from search_utils import search_peeps_local, get_peeps_image_url

print("=" * 60)
print("Testing Open Peeps Search: 'computer'")
print("=" * 60)

# Test 1: Search for "computer"
print("\n1. Searching for 'computer':")
results = search_peeps_local("computer", limit=5)

if results:
    print(f"   Found {len(results)} results:\n")
    for i, result in enumerate(results, 1):
        print(f"   {i}. {result['name']}")
        print(f"      Score: {result['score']}")
        print(f"      URL: {result['url']}")
        print(f"      Path: {result['path']}")
        print()
else:
    print("   No results found. Make sure index is built.")

# Test 2: Get best match
print("\n2. Best match for 'computer':")
best_url = get_peeps_image_url("computer")
if best_url:
    print(f"   ✅ Found: {best_url}")
else:
    print("   ❌ No match found")

# Test 3: Try related keywords
print("\n3. Testing related keywords:")
keywords = ["laptop", "technology", "device", "screen", "monitor"]
for keyword in keywords:
    url = get_peeps_image_url(keyword)
    if url:
        print(f"   '{keyword}' -> {url}")
    else:
        print(f"   '{keyword}' -> No match")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)

