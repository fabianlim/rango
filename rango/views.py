# Create your views here.
from django.http import HttpResponseRedirect, HttpResponse
from django.template import RequestContext
from django.shortcuts import render_to_response, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

# import the Category and Page models
from rango.models import Category, Page, UserProfile

# import the forms
from rango.forms import CategoryForm, PageForm, UserForm, UserProfileForm

# datetime
from datetime import datetime

# for running a bing query
from rango.bing_search import run_query

def encode_url(category_name):
    return category_name.replace(' ', '_')

def decode_url(category_url):
    return category_url.replace('_', ' ')

def get_category_list():
    category_list = Category.objects.all()
    for category in category_list:
        category.url = encode_url(category.name)

    return category_list

def index(request):
    context = RequestContext(request)

    context_dict = {'categories': get_category_list()}

    page_list = Page.objects.order_by('-views')[:5]
    context_dict['pages'] = page_list

    #### NEW CODE ####
    if request.session.get('last_visit'):
        # The session has a value for the last visit
        last_visit_time = request.session.get('last_visit')
        visits = request.session.get('visits', 0)
        # print "visits: {}, last visit {}".format (visits,last_visit_time)

        if (datetime.now() - datetime.strptime(last_visit_time[:-7], "%Y-%m-%d %H:%M:%S")).days > 0:
            request.session['visits'] = visits + 1
            request.session['last_visit'] = str(datetime.now())
    else:
        # The get returns None, and the session does not have a value for the last visit.
        request.session['last_visit'] = str(datetime.now())
        request.session['visits'] = 1
    #### END NEW CODE ####

    # Render and return the rendered response back to the user.
    return render_to_response('rango/index.html', context_dict, context)

def about(request):

    # Request our context from the request passed to us
    context = RequestContext(request)

    # If the visits session varible exists, take it and use it.
    # If it doesn't, we haven't visited the site so set the count to zero.
    if request.session.get('visits'):
        count = request.session.get('visits')
    else:
        count = 0

    # remember to include the visit data
    return render_to_response('rango/about.html', {'visits': count}, context)

def category(request, category_name_url):
    # Request our context from the request passed to us
    context = RequestContext(request)

    # extra context for displaying in sidebar
    cat_list = get_category_list()

    # Change underscores in the category name to spaces.
    # URLS don't handle spaces well, so we encode them as undersores
    # We can then simply replace the underscores with spaces again to get the name
    category_name = decode_url(category_name_url)

    # Create a context dictionary which we can pass to the template rendering engine
    # We start by containing the name of the category passed by the user
    context_dict = {'cat_list': cat_list, 'category_name': category_name}

    try:
        # Can we find a category with the given name?
        # If we can', the .get() method raises a DoesNotExist exception
        # So the .get() method returns one model instance or raises an exception
        category = Category.objects.get(name=category_name)

        # Retrieve all of the associated pages
        # Note that filter returns >=1 model instance
        pages = Page.objects.filter(category=category)
        pages = pages.order_by('-views')[:5] # show the 5 top views

        # Adds our results list to the template context under name pages
        context_dict['pages'] = pages
        # We also add the category object from the database to the context dictionary
        # We'll use this in the template to verify that the category exists
        context_dict['category'] = category

        # add this?
        context_dict['category_name_url'] = category_name_url

        if request.method == 'POST':
            try:
                query = request.POST['query'].strip()

                if query:
                    # Run our Bing function to get the results list!
                    result_list = run_query(query)

                # need to add the result_list in context
                context_dict['result_list'] = result_list
            except:
                pass

    except Category.DoesNotExist:
        # We get here if we didn't find the specified category
        # Don't do anything - the template displays the "no category" message for us
        pass


    # Go render the response and return it to the client
    return render_to_response('rango/category.html', context_dict, context)

@login_required
def like_category(request):
    context = RequestContext(request)
    cat_id = None
    if request.method == 'GET':
        cat_id = request.GET['category_id']

    likes = 0
    if cat_id:
        category = Category.objects.get(id=int(cat_id))
        if category:
            likes = category.likes + 1
            category.likes =  likes
            category.save()

    return HttpResponse(likes)

def add_category(request):
    # Get the context from the request.
    context = RequestContext(request)

    # A HTTP POST?
    if request.method == 'POST':
        form = CategoryForm(request.POST)

        # Have we been provided with a valid form?
        if form.is_valid():
            # Save the new category to the database.
            form.save(commit=True)

            # Now call the index() view.
            # The user will be shown the homepage.
            return HttpResponseRedirect('/rango/')
        else:
            # The supplied form contained errors - just print them to the terminal.
            print form.errors
    else:
        # If the request was not a POST, display the form to enter details.
        form = CategoryForm()

    # Bad form (or form details), no form supplied...
    # Render the form with error messages (if any).
    return render_to_response('rango/add_category.html', {'form': form}, context)


def add_page(request, category_name_url):
    context = RequestContext(request)

    category_name = decode_url(category_name_url)
    if request.method == 'POST':
        form = PageForm(request.POST)

        if form.is_valid():
            # This time we cannot commit straight away.
            # Not all fields are automatically populated!
            page = form.save(commit=False)

            # Retrieve the associated Category object so we can add it.
            # Wrap the code in a try block - check if the category actually exists!
            try:
                cat = Category.objects.get(name=category_name)
                page.category = cat
            except Category.DoesNotExist:
                # If we get here, the category does not exist.
                # Go back and render the add category form as a way of saying the category does not exist.
                return render_to_response('rango/add_category.html', {}, context)

            # Also, create a default value for the number of views.
            page.views = 0

            # With this, we can then save our new model instance.
            page.save()

            # Now that the page is saved, display the category instead.
            return category(request, category_name_url)
        else:
            print form.errors
    else:
        form = PageForm()

    return render_to_response( 'rango/add_page.html',
            {'category_name_url': category_name_url,
             'category_name': category_name, 'form': form},
             context)


def register(request):

    # Like before, get the request's context.
    context = RequestContext(request)

    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    registered = False

    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        user_form = UserForm(data=request.POST)
        profile_form = UserProfileForm(data=request.POST)

        # If the two forms are valid...
        if user_form.is_valid() and profile_form.is_valid():
            # Save the user's form data to the database.
            user = user_form.save()

            # Now we hash the password with the set_password method.
            # Once hashed, we can update the user object.
            user.set_password(user.password)
            user.save()

            # Now sort out the UserProfile instance.
            # Since we need to set the user attribute ourselves, we set commit=False.
            # This delays saving the model until we're ready to avoid integrity problems.
            profile = profile_form.save(commit=False)
            profile.user = user

            # Did the user provide a profile picture?
            # If so, we need to get it from the input form and put it in the UserProfile model.
            if 'picture' in request.FILES:
                profile.picture = request.FILES['picture']

            # Now we save the UserProfile model instance.
            profile.save()

            # Update our variable to tell the template registration was successful.
            registered = True

        # Invalid form or forms - mistakes or something else?
        # Print problems to the terminal.
        # They'll also be shown to the user.
        else:
            print user_form.errors, profile_form.errors

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        user_form = UserForm()
        profile_form = UserProfileForm()

    # Render the template depending on the context.
    return render_to_response(
            'rango/register.html',
            {'user_form': user_form, 'profile_form': profile_form, 'registered': registered},
            context)

def user_login(request):
    # Like before, obtain the context for the user's request.
    context = RequestContext(request)

    # If the request is a HTTP POST, try to pull out the relevant information.
    if request.method == 'POST':
        # Gather the username and password provided by the user.
        # This information is obtained from the login form.
        username = request.POST['username']
        password = request.POST['password']

        try:
            # check if user exists
            User.objects.get(username=username)

            # Use Django's machinery to attempt to see if the username/password
            # combination is valid - a User object is returned if it is.
            user = authenticate(username=username, password=password)

            # If we have a User object, the details are correct.
            # If None (Python's way of representing the absence of a value), no user
            # with matching credentials was found.
            if user:
                # Is the account active? It could have been disabled.
                if user.is_active:
                    # If the account is valid and active, we can log the user in.
                    # We'll send the user back to the homepage.
                    login(request, user)
                    return HttpResponseRedirect('/rango/')
                else:
                    # An inactive account was used - no logging in!
                    return HttpResponse("Your Rango account is disabled.")
            else:
                # Bad login details were provided. So we can't log the user in.
                print "Invalid password: {0}, {1}".format(username, password)
                # return HttpResponse("Invalid password.")
                return render_to_response('rango/login.html', {'bad_details':
                    "Invalid Password"}, context)

        except User.DoesNotExist:
            print "user {} does not exist".format(username)
            return render_to_response('rango/login.html', {'bad_details':
                    "User does not exist"}, context)


    # The request is not a HTTP POST, so display the login form.
    # This scenario would most likely be a HTTP GET.
    else:
        # No context variables to pass to the template system, hence the
        # blank dictionary object...
        return render_to_response('rango/login.html', {}, context)

@login_required
def restricted(request):
    context = RequestContext(request)
    return render_to_response('rango/restricted.html', {}, context)
    # return HttpResponse("Since you're logged in, you can see this text!")

# Use the login_required() decorator to ensure only those logged in can access the view.
@login_required
def user_logout(request):
    # Since we know the user is logged in, we can now just log them out.
    logout(request)

    # Take the user back to the homepage.
    return HttpResponseRedirect('/rango/')

def profile(request):
    context = RequestContext(request)

    if request.user.is_authenticated():
        return render_to_response('rango/profile.html', {'user_profile':
            request.user.userprofile}, context)
    else:
        return render_to_response('rango/profile.html', {}, context) #empty profile

def track_url(request):
    context = RequestContext(request)
    page_id = None
    url = '/rango/'
    if request.method == 'GET':
        if 'page_id' in request.GET:
            page_id = request.GET['page_id']
            try:
                page = Page.objects.get(id=page_id)
                page.views = page.views + 1
                page.save()
                url = page.url
            except:
                pass

    return redirect(url)

def get_category_list(max_results=0, starts_with=''):
        cat_list = []
        if starts_with:
                cat_list = Category.objects.filter(name__istartswith=starts_with)
        else:
                cat_list = Category.objects.all()

        if max_results > 0:
                if len(cat_list) > max_results:
                        cat_list = cat_list[:max_results]

        for cat in cat_list:
                cat.url = encode_url(cat.name)

        return cat_list

def suggest_category(request):
        context = RequestContext(request)
        cat_list = []
        starts_with = ''
        if request.method == 'GET':
                starts_with = request.GET['suggestion']

        cat_list = get_category_list(8, starts_with)

        return render_to_response('rango/category_list.html', {'cat_list': cat_list }, context)

@login_required
def auto_add_page(request):
    context = RequestContext(request)
    cat_id = None
    url = None
    title = None
    context_dict = {}
    if request.method == 'GET':
        cat_id = request.GET['category_id']
        url = request.GET['url']
        title = request.GET['title']
        if cat_id:
            category = Category.objects.get(id=int(cat_id))
            p = Page.objects.get_or_create(category=category, title=title, url=url)

            pages = Page.objects.filter(category=category).order_by('-views')

            # Adds our results list to the template context under name pages.
            context_dict['pages'] = pages

    return render_to_response('rango/page_list.html', context_dict, context)

