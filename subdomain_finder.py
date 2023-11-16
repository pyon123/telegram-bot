import requests

class SubdomainFinder:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://www.virustotal.com/vtapi/v2/domain/report"

    def get_subdomains(self, domain):
        params = {'apikey': self.api_key, 'domain': domain}
        response = requests.get(self.base_url, params=params)
        subdomains = []
        if response.status_code == 200:
            json_response = response.json()
            subdomains = json_response.get('subdomains', [])
        return subdomains

# This allows the script to be used as a module or standalone script
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python subdomain_finder.py <API_KEY> <DOMAIN>")
        sys.exit(1)

    api_key = sys.argv[1]
    domain = sys.argv[2]

    finder = SubdomainFinder(api_key)
    subdomains = finder.get_subdomains(domain)
    if subdomains:
        print(f"Subdomains for {domain}:")
        for subdomain in subdomains:
            print(subdomain)
    else:
        print(f"No subdomains found for {domain}.")
