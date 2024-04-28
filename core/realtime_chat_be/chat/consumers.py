from channels.generic.websocket import WebsocketConsumer
from asgiref.sync import async_to_sync
from django.core.files.base import ContentFile
from django.db.models import Q, Exists, OuterRef
from django.db.models.functions import Coalesce 
from .models import User, Connection, Message
from .serializers import (UserSerializer,
                           SearchSerializer,
                             RequestSerializer,
                               FriendSerializer, 
                               MessageSerializer)
import json
import base64

class ChatComsumer(WebsocketConsumer):

    def connect(self):
        user = self.scope['user']
        print(user, user.is_authenticated)
        if not user.is_authenticated:
            return
        
        #save username to user as a group name for this user
        self.username = user.username
        #Join this user to group with their username
        async_to_sync(self.channel_layer.group_add)(
            self.username, self.channel_name
        )

        self.accept()

    def disconnect(self, code):
        #   left room/group
        async_to_sync(self.channel_layer.group_discard)(
            self.username, self.channel_name
        )

    #-----------------------
    #    Handle requests
    #-----------------------
    def receive(self, text_data): #place recieve all requests
        # Receive mesage from websocket
        data = json.loads(text_data)
        data_source = data.get('source')
        print('receive', json.dumps(data, indent=2))

        # Get friend list
        if data_source == 'friend.list':
            self.receive_friend_list(data)

        # Message list
        if data_source == 'message.list':
            self.receive_message_list(data)

        # Message has been sent
        if data_source == 'message.send':
            self.receive_message_send(data)
        
        # Message has been sent
        if data_source == 'message.type':
            self.receive_message_type(data)

        # Accept friend requests
        elif data_source == 'request.accept':
            self.receive_request_accept(data)

        # make friend requests
        elif data_source == 'request.connect':
            self.receive_request_connect(data)
        
        # Get request list
        elif data_source == 'request.list':
            self.receive_request_list(data)
        
        # search request
        elif data_source == 'search':
            self.receive_search(data)

        # thumbnail upload
        elif data_source == 'thumbnail':
            self.receive_thumbnail(data)

    ##########################
    # nếu có thời gian mình sẽ custom chỗ search này lên thành search theo
    # user name hoặc search theo name, cái nào trùng thì hiện ra

    def receive_search(self, data):
        query = data.get('query')
        # Get users from query search term
        Users = User.objects.filter(
            Q(username__istartswith=query) |
            Q(first_name__istartswith=query) |
            Q(last_name__istartswith=query)
        ).exclude(   #search nên loại trừ chính mình ra
            username=self.username
        ).annotate(     # nếu mà nó đã tồn tại connection thì check xem nó là loại gì?
            pending_them = Exists(  #   là mình add nso hay nó add mình
                Connection.objects.filter(
                    sender = self.scope['user'],
                    receiver = OuterRef('id'),
                    accepted = False
                )
            ),
            pending_me = Exists(
                Connection.objects.filter(
                    sender = OuterRef('id'),
                    receiver = self.scope['user'],
                    accepted = False
                ),
            ),
            connected = Exists(
                Connection.objects.filter(
                    Q(sender=self.scope['user'], receiver=OuterRef('id')) |
                    Q(receiver=self.scope['user'], sender=OuterRef('id')),
                    accepted=True
                ),
            )
        )
        # serialize result
        serialized = SearchSerializer(Users, many=True)
        # send search result back to this user
        self.send_group(self.username, 'search', serialized.data)

    #   receive message list
    def receive_message_list(self, data):
        user = self.scope['user']
        connectionId = data.get('connectionId')
        page = data.get('page')
        page_size = 15

        try:
            connection = Connection.objects.get(id=connectionId)
        except Connection.DoesNotExist:
            print('Error: couldnt fint connection')
            return
        #   get messages
        messages = Message.objects.filter(
            connection=connection
        ).order_by('-created')[page * page_size:(page + 1) * page_size]
        #   serialized messages
        serialized_message = MessageSerializer(
            messages,
            context={
                'user': user
            },
            many=True
        )
        #   get recipient friend
        recipient = connection.sender
        if connection.sender == user:
            recipient = connection.receiver

        #   serialize friend
        serialized_friend = UserSerializer(recipient)

        #   count the total number of messages for this connection
        messages_count = Message.objects.filter(
            connection=connection
        ).count()

        next_page = page + 1 if messages_count > (page + 1)*page_size else None

        data = {
            'messages': serialized_message.data,
            'next': next_page,
            'friend': serialized_friend.data,
        }
        #   send back to the requestor
        self.send_group(user.username, 'message.list', data)


    #   receive message send
    def receive_message_send(self, data):
        user = self.scope['user']
        connectionId = data.get('connectionId')
        message_text = data.get('message')
        try:
            connection = Connection.objects.get(
                id = connectionId
            )
        except Connection.DoesNotExist:
            print('Error: couldnt fint connection')
            return
        
        message = Message.objects.create(
            connection=connection,
            user=user,
            text=message_text
        )


        #   get recipient friend
        recipient = connection.sender
        if connection.sender == user:
            recipient = connection.receiver
        #   send new message back to sender
        serialized_message = MessageSerializer(
            message,
            context={
                'user': user
            }
        )
        serialized_friend = UserSerializer(recipient)
        data = {
            'message': serialized_message.data,
            'friend': serialized_friend.data,
        }
        self.send_group(user.username, 'message.send', data)
        #
        #   send new message to receiver
        serialized_message = MessageSerializer(
            message,
            context={
                'user': recipient
            }
        )
        serialized_friend = UserSerializer(user)
        data = {
            'message': serialized_message.data,
            'friend': serialized_friend.data,
        }
        self.send_group(recipient.username, 'message.send', data)


    #   message type
    def receive_message_type(self, data):
        user = self.scope['user']
        recipient_username = data.get('username')
        data = {
            'username': user.username
        }
        self.send_group(recipient_username, 'message.type', data)


    #   accept friend request
    def receive_request_accept(self, data):
        username = data.get('username')
        #   Featch conenction object
        try:
            connection = Connection.objects.get(
                sender__username=username,
                receiver=self.scope['user']
            )
        except Connection.DoesNotExist:
            print('Error connection doesnt exists')
            return
        #   update the connection
        connection.accepted = True
        connection.save()
        
        serialized = RequestSerializer(connection)
        #   send accepted request to sender
        self.send_group(
            connection.sender.username, 'request.accept', serialized.data
        )
        #   send accepted request to receiver
        self.send_group(
            connection.receiver.username, 'request.accept', serialized.data
        )

        #   send new frined object to sender
        serialized_friend = FriendSerializer(
            connection,
            context={
                'user': connection.sender
            }
        )
        self.send_group(
            connection.sender.username, 'friend.new', serialized_friend.data)
        
        #   send new frined object to receiver
        serialized_friend = FriendSerializer(
            connection,
            context={
                'user': connection.receiver
            }
        )
        self.send_group(
            connection.receiver.username, 'friend.new', serialized_friend.data)


    #### make friend request
    def receive_request_connect(self, data):
        username = data.get('username')  # take username from data sent by user
        #  Attempt to fetch the receiving user
        try:
            receiver = User.objects.get(username=username)
        except User.DoesNotExist:
            print('Error: user not found!')
            return
        # create connection
        connection, _ = Connection.objects.get_or_create(
            sender = self.scope['user'], # người gửi
            receiver = receiver # người nhận
        )
        # serializer conenction
        serialized = RequestSerializer(connection)
        # send back to sender
        self.send_group(
            connection.sender.username, 'request.connect', serialized.data)
        # send to receiver
        self.send_group(
            connection.receiver.username, 'request.connect', serialized.data)

    ### make friend list
    def receive_friend_list(self, data):
        user = self.scope['user']
        #   lastest message subquery
        lastest_message = Message.objects.filter(
            connection = OuterRef('id')
        ).order_by('-created')[:1] # dùng slice cắt thằng đầu tiên
        #   get connection for user
        connections = Connection.objects.filter(
            Q(sender=user) | Q(receiver=user),
            accepted = True
        ).annotate( #   lấy giá trị từ object latest message
            lastest_text = lastest_message.values('text'),
            lastest_created = lastest_message.values('created')
        ).order_by(
            Coalesce('lastest_created', 'updated_date').desc()
        )
        serialized = FriendSerializer(
            connections,
            context={
                'user': user
            },
            many=True
        )
        #   send data back to requesting user
        self.send_group(user.username, 'friend.list', serialized.data)

    ### get friends request
    def receive_request_list(self, data):
        # lấy user đang đăng nhập
        user = self.scope['user']
        # get conenction get to this user
        connections = Connection.objects.filter(
            receiver = user,
            accepted = False
        )
        serialized = RequestSerializer(connections, many=True)
        self.send_group(user.username, 'request.list', serialized.data)

    #### set avatar
    def receive_thumbnail(self, data):
        user = self.scope['user']
        # convert base64 data to django content file
        image_str = data.get('base64')
        image = ContentFile(base64.b64decode(image_str))
        # update thumbnail field
        filename = data.get('filename')
        user.thumbnail.save(filename, image, save=True)
        # serializer user
        serialized = UserSerializer(user)
        # send update user data including new thumbnail
        self.send_group(self.username, 'thumbnail', serialized.data)

    #------------------------------------------------
    #      Catch/all broadcast to client helpers
    #------------------------------------------------
    def send_group(self, group, source, data):
        response = {
            'type': 'broadcast_group',
            'source': source,
            'data': data
        }

        async_to_sync(self.channel_layer.group_send)(
            group, response
        )
    def broadcast_group(self, data):
        '''
        data:
            - type: 'broadcast_group'
            - source: where is originated from
            - data: what ever you want to send as a dict
        '''
        data.pop('type')
        '''
        return data:
            - source: where is originated from
            - data: what ever you want to send as a dict
        '''
        self.send(text_data=json.dumps(data))
    