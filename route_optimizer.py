class DeliveryLocation:
    def __init__(self, id, latitude, longitude):
        self.id = id
        self.latitude = latitude
        self.longitude = longitude

class RouteOptimizer:
    def __init__(self, depot):
        self.depot = depot
    
    def optimize_route(self, delivery_locations):
        if not delivery_locations:
            return [self.depot, self.depot]  # Just return depot if no deliveries
        
        # Simple nearest neighbor algorithm for sequencing
        current_location = self.depot
        route = [self.depot]
        remaining_locations = delivery_locations.copy()
        
        while remaining_locations:
            nearest = min(remaining_locations, 
                          key=lambda loc: self.calculate_distance(current_location, loc))
            route.append(nearest)
            current_location = nearest
            remaining_locations.remove(nearest)
        
        # Add depot as final destination
        route.append(self.depot)
        return route
    
    def calculate_distance(self, loc1, loc2):
        # Simple distance calculation
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth's radius in km
        lat1, lon1 = radians(loc1.latitude), radians(loc1.longitude)
        lat2, lon2 = radians(loc2.latitude), radians(loc2.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance
    
    def get_route_details(self, route):
        details = {
            "total_distance": 0,
            "total_time": 0,
            "segments": []
        }
        
        for i in range(len(route) - 1):
            # Calculate distance between consecutive points
            distance = self.calculate_distance(route[i], route[i+1])
            
            # Estimate time (assuming average speed of 20 km/h in city traffic)
            time_mins = (distance / 20) * 60
            
            details["total_distance"] += distance
            details["total_time"] += time_mins
            
            # Add segment details
            details["segments"].append({
                "origin_id": route[i].id,
                "destination_id": route[i+1].id,
                "distance": distance,
                "duration": time_mins
            })
        
        return details