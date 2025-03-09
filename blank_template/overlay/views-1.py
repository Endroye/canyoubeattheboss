import json
from django.http import JsonResponse

def overlay_data(request):
    with open('/home/Endroye/canyoubeattheboss/overlay_data.json', 'r') as file:
        data = json.load(file)
    return JsonResponse(data)
