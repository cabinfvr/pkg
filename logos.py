import os
import json

class Logos:
    def __init__(self, json_path='logos.json'):
        if not os.path.isabs(json_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(base_dir, json_path)
        with open(json_path, 'r') as f:
            self.logos = json.load(f)
    
    def get_options(self):
        return list(self.logos.keys())
    
    def get_brand(self, brand_name):
        return self.logos.get(brand_name, {})
    
    def get_social_starter(self, brand_name):
        return self.logos.get(brand_name, {}).get('social_starter')
    
    def get_bxl_class(self, brand_name):
        return self.logos.get(brand_name, {}).get('bxl_class')
    
    def get_all(self):
        """Return list of logo objects with name and bxl_class attributes for template use"""
        logo_list = []
        for name, config in self.logos.items():
            logo_obj = type('Logo', (), {
                'name': name,
                'bxl_class': config.get('bxl_class', f'bx-{name}')
            })()
            logo_list.append(logo_obj)
        return logo_list
    
    def get_all_dict(self):
        """Return the original dictionary format if needed elsewhere"""
        return self.logos