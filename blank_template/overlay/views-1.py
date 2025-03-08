 from django.http import JsonResponse
import json

def overlay_data(request):
    with open('overlay_data.json', 'r') as file:
        data = json.load(file)
    return JsonResponse(data)
