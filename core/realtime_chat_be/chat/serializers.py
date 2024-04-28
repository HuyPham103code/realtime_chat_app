from rest_framework import serializers
from .models import User, Connection, Message

class SignUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',    
            'password'
        ]
        extra_kwargs = {
            'password': {
                #Ensure that when serializeing, this field will be excluded
                'write_only': True
            }
        }

    def create(self, validated_data):
        #clean all values, set as lowercase
        username = validated_data['username'].lower()
        first_name = validated_data['first_name'].lower()
        last_name = validated_data['last_name'].lower()
        #create new user
        user = User.objects.create(
            username = username,
            first_name = first_name,
            last_name = last_name
        )
        password = validated_data['password']
        user.set_password(password)
        user.save()
        return user
        


class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField() #combine fName and lName
    class Meta:
        model = User
        fields = [
            'username',
            'name',
            # 'first_name',
            # 'last_name',
            'thumbnail'
        ]

    def get_name(self, obj):
        fname = obj.first_name.capitalize()
        lname = obj.last_name.capitalize()
        return fname + ' ' + lname
    
class SearchSerializer(UserSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'username',
            'name',
            'thumbnail',
            'status'
        ]
    def get_status(self, obj):
        if obj.pending_them:
            return 'pending-them'
        elif obj.pending_me:
            return 'pending-me'
        elif obj.connected:
            return 'connected'
        return 'no-connection'
    
class RequestSerializer(serializers.ModelSerializer):
    sender = UserSerializer()
    receiver = UserSerializer()
    class Meta:
        model = Connection
        fields = [
            'id',
            'sender',
            'receiver',
            'created_date'
        ]

class FriendSerializer(serializers.ModelSerializer):
    friend = serializers.SerializerMethodField()
    preview = serializers.SerializerMethodField()
    updated_date = serializers.SerializerMethodField()

    class Meta:
        model = Connection
        fields = [
            'id',
            'friend',
            'preview',
            'updated_date'
        ] 
    
    def get_friend(self, obj):
        #   If I am the sender
        if self.context['user'] == obj.sender:
            return UserSerializer(obj.receiver).data
        #   If I am the receiver
        elif self.context['user'] == obj.receiver:
            return UserSerializer(obj.sender).data
        else:
            print('Error: no User found in friendserializer')

    def get_preview(self, obj):
        if not hasattr(obj, 'lastest_text') or obj.lastest_text is None:
            return 'New conenction'
        return obj.lastest_text
    
    def get_updated_date(self, obj):
        if not hasattr(obj, 'lastest_created'):
            date = obj.updated_date
        else:
            date = obj.lastest_created or obj.updated_date
        return date.isoformat()

class MessageSerializer(serializers.ModelSerializer):
    is_me = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [  
            'id',
            'is_me',
            'text',
            'created'
        ]
    def get_is_me(self, obj):
        return self.context['user'] == obj.user
