
class UserManagementClient:
    def __init__(self):
        self.groups = {}

    @staticmethod
    def get_config():
        return {}   
    
    @staticmethod
    def test_config():
        pass

    def add_user_to_group(self, user, group):
        if group not in self.groups.keys():
            self.groups[group] = set()
        self.groups[group].add(user)
        return True

    def remove_user_from_group(self, user, group):
        if group not in self.groups.keys():
            return False
        if user not in self.groups[group]:
            return False
        self.groups[group].remove(user)
        return True

    def user_in_group(self, user, group):
        return group in self.groups and user in self.groups[group]

    def group_exists(self, group):
        return group in self.groups.keys()
    
    def get_group_members(self, group):
        if group in self.groups:
            return list(self.groups[group])
        return []

    def create_group(self, group):
        if group in self.groups:
            return False
        self.groups[group] = set()
        return True
    