from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import HelpArticle, HelpLike, HelpComment
from .serializers import HelpArticleSerializer, HelpLikeSerializer, HelpCommentSerializer, HelpArticleCreateSerializer, HelpCommentCreateSerializer
from accounts.models import User
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes
from django.db.models import Count
from accounts.models import User

################################################
# 질문 게시판
# 질문 게시판 글 리스트 및 생성
@api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
def help_article_list(request):
    if request.method == 'GET':
        articles = HelpArticle.objects.all().order_by('-id')
        serializer = HelpArticleSerializer(articles, many=True)
        
        # 각 게시글에 좋아요 수 추가
        data = serializer.data
        for article_data in data:
            article_likes = HelpLike.objects.filter(help_article_id=article_data['id']).count()
            article_data['like_count'] = article_likes
            
        return Response(data)

    elif request.method == 'POST':
        serializer = HelpArticleCreateSerializer(data=request.data)
        try:
            if serializer.is_valid(raise_exception=True):
                serializer.save(user=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


# 질문 게시판 글 상세 조회, 수정 및 삭제
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def help_article_detail(request, pk):
    article = get_object_or_404(HelpArticle, pk=pk)

    if request.method == 'GET':
        serializer = HelpArticleSerializer(article)
        data = serializer.data
        data['like_count'] = HelpLike.objects.filter(help_article=article).count()
        data['is_liked'] = HelpLike.objects.filter(
            help_article=article,
            user=request.user
        ).exists()
        data['is_author'] = article.user.id == request.user.id
        data['user_id'] = article.user.id
        return Response(data)
        # return Response(serializer.data)

    # PUT, DELETE 작성자만 가능
    # if request.user != article.user:
    #     return Response(
    #         {'error': '작성자만 수정/삭제할 수 있습니다.'},
    #         status=status.HTTP_403_FORBIDDEN
    #     )
    
    if request.method == 'PUT':
        serializer = HelpArticleSerializer(article, data=request.data, partial=True)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data)

    elif request.method == 'DELETE':
        article.delete()
        return Response({'message': f'질문 {article.help_title}이 삭제되었습니다.'}, status=status.HTTP_204_NO_CONTENT)


# 좋아요
@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def help_like_toggle(request, pk):
    article = get_object_or_404(HelpArticle, pk=pk)
    like = HelpLike.objects.filter(user=request.user, help_article=article)
    
    # 좋아요가 이미 있으면 취소
    if like.exists():
        like.delete()
        like_count = HelpLike.objects.filter(help_article=article).count()
        return Response({
            'like_count': like_count,
            'is_liked': False
        }, status=status.HTTP_200_OK)
    
    # 좋아요가 없으면 생성
    else:
        HelpLike.objects.create(user=request.user, help_article=article)
        like_count = HelpLike.objects.filter(help_article=article).count()
        return Response({
            'like_count': like_count,
            'is_liked': True
        }, status=status.HTTP_201_CREATED)


# 댓글 리스트 및 생성
@api_view(['GET', 'POST'])
def help_comment_list_create(request, pk=None):
    if request.method == 'GET':
        comments = HelpComment.objects.filter(help_article_id=pk)
        serializer = HelpCommentSerializer(comments, many=True)
        data = serializer.data

        # 각 댓글에 작성자 여부(is_author) 추가
        for comment in data:
            comment['is_author'] = comment['user']['id'] == request.user.id
        return Response(data)

    elif request.method == 'POST':
        article = get_object_or_404(HelpArticle, pk=pk)
        serializer = HelpCommentCreateSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            comment = serializer.save()

            # 생성된 댓글 데이터에 is_author 필드 추가
            response_data = HelpCommentSerializer(comment).data
            response_data['is_author'] = True  # 생성자는 항상 작성자
            return Response(response_data, status=status.HTTP_201_CREATED)


# 댓글 상세 조회, 수정 및 삭제
@api_view(['GET', 'PUT', 'DELETE'])
def help_comment_detail(request, pk):
    comment = get_object_or_404(HelpComment, pk=pk)

    # 상세 조회
    if request.method == 'GET':
        serializer = HelpCommentSerializer(comment)
        data = serializer.data
        data['is_author'] = comment.user == request.user  # 작성자 여부 추가
        return Response(data)

    # 수정
    elif request.method == 'PUT':
        # if comment.user != request.user:
        #     return Response({'detail': '수정 권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = HelpCommentCreateSerializer(comment, data=request.data, partial=True)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data)

    # 삭제
    elif request.method == 'DELETE':
        # if comment.user != request.user:
        #     return Response({'detail': '삭제 권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        comment.delete()
        return Response({'message': '댓글이 삭제되었습니다.'}, status=status.HTTP_204_NO_CONTENT)
    

################################################
# 메인 페이지 - HOT 게시글
@api_view(['GET'])
def hot_articles(request):
    # 좋아요 수를 기준으로 상위 3개 게시글 가져오기
    articles = HelpArticle.objects.annotate(
        like_count=Count('helplike')
    ).order_by('-like_count')[:3]
    
    serializer = HelpArticleSerializer(articles, many=True)
    data = serializer.data
    
    # 각 게시글의 좋아요 수 추가
    for article_data, article in zip(data, articles):
        article_data['like_count'] = article.like_count
        
    return Response(data)