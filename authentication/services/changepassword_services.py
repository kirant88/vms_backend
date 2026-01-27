from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist

User = get_user_model()


class ChangePassword:
    @staticmethod
    def get_user_by_email(email):
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            raise ObjectDoesNotExist("User not found")

    @staticmethod
    def update_password(user, new_password):
        user.set_password(new_password)
        user.save()
        return user
