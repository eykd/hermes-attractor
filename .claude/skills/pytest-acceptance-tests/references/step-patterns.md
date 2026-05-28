# Step Definition Patterns by Domain

Common step definition implementations for Django acceptance tests.

## Authentication Steps

### Login/Logout

```python
from pytest_bdd import given, when, then, parsers
from django.contrib.auth import get_user_model

User = get_user_model()

@given("I am logged in", target_fixture="current_user")
def logged_in_user(browser, live_server, django_user_model):
    """Generic login."""
    user = django_user_model.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )
    browser.visit(f'{live_server.url}/accounts/login/')
    browser.fill('username', 'testuser')
    browser.fill('password', 'testpass123')
    browser.find_by_css('button[type="submit"]').first.click()
    return user


@given(parsers.parse('I am logged in as "{email}"'), target_fixture="current_user")
def login_as(browser, live_server, django_user_model, email):
    """Login with specific email."""
    user = django_user_model.objects.create_user(
        username=email.split('@')[0],
        email=email,
        password='testpass123'
    )
    browser.visit(f'{live_server.url}/accounts/login/')
    browser.fill('email', email)
    browser.fill('password', 'testpass123')
    browser.find_by_css('button[type="submit"]').first.click()
    return user


@given("I am logged in as an admin", target_fixture="admin_user")
def logged_in_admin(browser, live_server, admin_user):
    """Login as admin."""
    browser.visit(f'{live_server.url}/admin/login/')
    browser.fill('username', admin_user.username)
    browser.fill('password', 'password')  # Default admin password
    browser.find_by_css('button[type="submit"]').first.click()
    return admin_user


@given("I am not logged in")
def not_logged_in(browser):
    """Ensure logged out."""
    # Browser starts fresh, but verify
    assert not browser.is_element_present_by_css('.user-menu')


@when("I log out")
def logout(browser):
    """Perform logout."""
    browser.find_by_css('a[href*="logout"]').first.click()


@then("I should be logged in")
def verify_logged_in(browser):
    """Verify authenticated state."""
    assert browser.is_element_present_by_css('.user-menu')


@then("I should be logged out")
def verify_logged_out(browser):
    """Verify not authenticated."""
    assert not browser.is_element_present_by_css('.user-menu')
    assert browser.is_element_present_by_css('a[href*="login"]')
```

### Permission Checks

```python
@given(parsers.parse('I am logged in as {role}'), target_fixture="role_user")
def login_with_role(browser, live_server, django_user_model, role):
    """Login with specific role."""
    user = django_user_model.objects.create_user(
        username=f'{role}_user',
        email=f'{role}@example.com',
        password='testpass'
    )

    if role == 'admin':
        user.is_superuser = True
        user.is_staff = True
    elif role == 'staff':
        user.is_staff = True

    user.save()

    # Login
    browser.visit(f'{live_server.url}/accounts/login/')
    browser.fill('username', user.username)
    browser.fill('password', 'testpass')
    browser.find_by_css('button[type="submit"]').first.click()

    return user


@then("I should see permission denied")
def see_permission_denied(browser):
    """Check for permission error."""
    assert browser.is_text_present('Permission denied') or \
           browser.is_text_present('403 Forbidden') or \
           browser.status_code == 403
```

## Navigation Steps

```python
@given(parsers.parse('I am on the {page} page'))
@when(parsers.parse('I visit the {page} page'))
def visit_page(browser, live_server, page):
    """Visit named page."""
    page_urls = {
        'home': '/',
        'login': '/accounts/login/',
        'register': '/accounts/register/',
        'dashboard': '/dashboard/',
        'profile': '/profile/',
        'new article': '/articles/new/',
        'articles': '/articles/',
    }
    url = page_urls.get(page.lower(), f'/{page}/')
    browser.visit(f'{live_server.url}{url}')


@when(parsers.parse('I visit "{url}"'))
def visit_url(browser, live_server, url):
    """Visit specific URL."""
    browser.visit(f'{live_server.url}{url}')


@when("I click back")
def click_back(browser):
    """Browser back button."""
    browser.back()


@when("I reload the page")
def reload(browser):
    """Refresh page."""
    browser.reload()


@then(parsers.parse('I should be on the {page} page'))
def verify_on_page(browser, page):
    """Verify current page."""
    page_patterns = {
        'home': '/',
        'login': '/login',
        'dashboard': '/dashboard',
        'profile': '/profile',
    }
    pattern = page_patterns.get(page.lower(), f'/{page}')
    assert pattern in browser.url


@then(parsers.parse('I should be redirected to "{url}"'))
def verify_redirect(browser, url):
    """Verify redirect occurred."""
    assert url in browser.url
```

## Form Interaction Steps

```python
@when(parsers.parse('I enter {field} "{value}"'))
def enter_field(browser, field, value):
    """Fill a form field."""
    browser.fill(field, value)


@when(parsers.parse('I enter "{value}" in the {field} field'))
def enter_field_alt(browser, field, value):
    """Alternative syntax."""
    browser.fill(field, value)


@when(parsers.parse('I check "{checkbox}"'))
def check_checkbox(browser, checkbox):
    """Check a checkbox."""
    browser.check(checkbox)


@when(parsers.parse('I uncheck "{checkbox}"'))
def uncheck_checkbox(browser, checkbox):
    """Uncheck a checkbox."""
    browser.uncheck(checkbox)


@when(parsers.parse('I select "{value}" from {field}'))
def select_option(browser, value, field):
    """Select from dropdown."""
    browser.select(field, value)


@when(parsers.parse('I choose "{value}" for {field}'))
def choose_radio(browser, value, field):
    """Select radio button."""
    browser.choose(field, value)


@when("I submit the form")
def submit_form(browser):
    """Submit current form."""
    browser.find_by_css('button[type="submit"]').first.click()


@when(parsers.parse('I click "{button_text}"'))
def click_button(browser, button_text):
    """Click button by text."""
    browser.find_by_text(button_text).first.click()


@when(parsers.parse('I click the {button_name} button'))
def click_named_button(browser, button_name):
    """Click button by name."""
    browser.find_by_name(button_name).first.click()


@when("I fill in the form:")
def fill_form_table(browser, datatable):
    """Fill form from data table.

    Example:
        | field    | value           |
        | email    | test@email.com  |
        | password | secret123       |
    """
    for row in datatable:
        browser.fill(row['field'], row['value'])
```

## File Upload Steps

```python
import tempfile
from pathlib import Path

@when(parsers.parse('I upload a {size}MB {filetype} image'))
def upload_image(browser, size, filetype):
    """Upload image file."""
    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix=f'.{filetype}', delete=False) as f:
        # Write dummy data (not real image)
        f.write(b'x' * (int(size) * 1024 * 1024))
        filepath = f.name

    browser.attach_file('image', filepath)

    # Cleanup
    Path(filepath).unlink()


@when(parsers.parse('I attempt to upload a {filetype} file'))
def upload_file_type(browser, filetype):
    """Upload specific file type."""
    with tempfile.NamedTemporaryFile(suffix=f'.{filetype}', delete=False) as f:
        f.write(b'test content')
        filepath = f.name

    browser.attach_file('file', filepath)
    Path(filepath).unlink()
```

## Assertion Steps

```python
@then(parsers.parse('I should see "{text}"'))
def see_text(browser, text):
    """Verify text is present."""
    assert browser.is_text_present(text), f"Text '{text}' not found"


@then(parsers.parse('I should not see "{text}"'))
def not_see_text(browser, text):
    """Verify text is not present."""
    assert not browser.is_text_present(text), f"Text '{text}' should not be visible"


@then(parsers.parse('the page title should be "{title}"'))
def check_title(browser, title):
    """Verify page title."""
    assert browser.title == title


@then(parsers.parse('I should see a {css_class} message'))
def see_message_type(browser, css_class):
    """Verify message type (success, error, warning)."""
    assert browser.is_element_present_by_css(f'.{css_class}')


@then("I should see an error message")
def see_error(browser):
    """Verify error message present."""
    assert browser.is_element_present_by_css('.error') or \
           browser.is_element_present_by_css('.alert-danger')


@then("I should see a success message")
def see_success(browser):
    """Verify success message."""
    assert browser.is_element_present_by_css('.success') or \
           browser.is_element_present_by_css('.alert-success')


@then(parsers.parse('I should see {count:d} {items}'))
def count_items(browser, count, items):
    """Count elements on page."""
    # Convert item name to CSS class
    css_class = f'.{items.replace(" ", "-")}'
    elements = browser.find_by_css(css_class)
    assert len(elements) == count, f"Expected {count} {items}, found {len(elements)}"
```

## Django Model Steps

```python
from myapp.models import Article, Category

@given(parsers.parse('there is a category "{name}"'), target_fixture="category")
def create_category(db, name):
    """Create category."""
    return Category.objects.create(
        name=name,
        slug=name.lower().replace(' ', '-')
    )


@given(parsers.parse('I have an article titled "{title}"'), target_fixture="article")
def create_article(db, current_user, category, title):
    """Create article for current user."""
    return Article.objects.create(
        title=title,
        slug=title.lower().replace(' ', '-'),
        content='Test content',
        author=current_user,
        category=category
    )


@given("there are articles:", target_fixture="articles")
def create_articles_table(db, datatable):
    """Create articles from data table.

    Example:
        | title       | status    |
        | Article 1   | published |
        | Article 2   | draft     |
    """
    articles = []
    for row in datatable:
        article = Article.objects.create(
            title=row['title'],
            slug=row['title'].lower().replace(' ', '-'),
            content='Test content',
            status=row.get('status', 'draft')
        )
        articles.append(article)
    return articles


@then(parsers.parse('the {model} should be saved to the database'))
def verify_model_saved(db, model):
    """Verify model instance exists."""
    from django.apps import apps
    Model = apps.get_model('myapp', model)
    assert Model.objects.exists()


@then(parsers.parse('the article should be {status}'))
def verify_article_status(article, status):
    """Verify article status."""
    article.refresh_from_db()
    assert article.status == status


@then(parsers.parse('the {model} should not exist'))
def verify_not_exists(db, model):
    """Verify model deleted."""
    from django.apps import apps
    Model = apps.get_model('myapp', model)
    assert not Model.objects.exists()


@then(parsers.parse('{count:d} {models} should be created'))
def verify_count_created(db, count, models):
    """Verify count of created models."""
    from django.apps import apps
    # Convert plural to singular and get model
    model_name = models.rstrip('s')
    Model = apps.get_model('myapp', model_name)
    assert Model.objects.count() == count
```

## Email Steps

```python
from django.core import mail

@then("I should receive an email")
def verify_email_sent():
    """Verify any email was sent."""
    assert len(mail.outbox) > 0


@then(parsers.parse('I should receive an email at "{email}"'))
def verify_email_to(email):
    """Verify email sent to address."""
    assert len(mail.outbox) > 0
    assert email in mail.outbox[-1].to


@then(parsers.parse('the email subject should be "{subject}"'))
def verify_email_subject(subject):
    """Verify email subject."""
    assert len(mail.outbox) > 0
    assert mail.outbox[-1].subject == subject


@then(parsers.parse('the email should contain "{text}"'))
def verify_email_content(text):
    """Verify email body contains text."""
    assert len(mail.outbox) > 0
    assert text in mail.outbox[-1].body


@given("I have received a verification email", target_fixture="verification_email")
def get_verification_email():
    """Get last sent email."""
    assert len(mail.outbox) > 0
    return mail.outbox[-1]


@when("I click the verification link in the email")
def click_email_link(browser, live_server, verification_email):
    """Extract and visit link from email."""
    import re
    # Extract URL from email body
    pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(pattern, verification_email.body)

    if urls:
        # Replace domain with live_server
        url = urls[0]
        path = url.split('/', 3)[-1] if '/' in url else ''
        browser.visit(f'{live_server.url}/{path}')
```

## Search & Filter Steps

```python
@when(parsers.parse('I search for "{query}"'))
def search(browser, query):
    """Perform search."""
    browser.fill('q', query)
    browser.find_by_css('button[type="submit"]').first.click()


@when(parsers.parse('I filter by {field} "{value}"'))
def filter_by(browser, field, value):
    """Apply filter."""
    browser.select(f'filter_{field}', value)


@when(parsers.parse('I sort by "{sort_option}"'))
def sort_by(browser, sort_option):
    """Apply sorting."""
    browser.select('sort', sort_option)


@then("I should see search results")
def see_results(browser):
    """Verify results present."""
    assert browser.is_element_present_by_css('.search-result')


@then('I should see "No results found"')
def see_no_results(browser):
    """Verify no results message."""
    assert browser.is_text_present('No results found') or \
           not browser.is_element_present_by_css('.search-result')
```

## Pagination Steps

```python
@then(parsers.parse('I should see {count:d} items'))
def verify_item_count(browser, count):
    """Verify number of items on page."""
    items = browser.find_by_css('.item')
    assert len(items) == count


@then(parsers.parse('I should see "Page {page:d} of {total:d}"'))
def verify_page_indicator(browser, page, total):
    """Verify pagination indicator."""
    assert browser.is_text_present(f'Page {page} of {total}')


@when("I click next page")
def click_next(browser):
    """Go to next page."""
    browser.find_link_by_text('Next').first.click()


@when("I click previous page")
def click_previous(browser):
    """Go to previous page."""
    browser.find_link_by_text('Previous').first.click()


@when(parsers.parse('I click page {page:d}'))
def click_page(browser, page):
    """Go to specific page."""
    browser.find_link_by_text(str(page)).first.click()
```

## AJAX/Dynamic Content Steps

```python
import time

@when(parsers.parse('I wait {seconds:d} seconds'))
def wait_seconds(seconds):
    """Explicit wait."""
    time.sleep(seconds)


@when("I wait for the page to load")
def wait_for_load(browser):
    """Wait for common loading indicators."""
    # Wait for loading spinner to disappear
    import time
    for _ in range(10):
        if not browser.is_element_present_by_css('.loading'):
            break
        time.sleep(0.5)


# Note: Django driver doesn't execute JavaScript
# For AJAX, test the endpoint directly with Django test client
@when("I click load more")
def load_more_ajax(client):
    """Test AJAX endpoint directly."""
    response = client.get('/api/items/?page=2')
    assert response.status_code == 200
    # Verify data structure
    data = response.json()
    assert 'results' in data
```

## Using Fixtures in Steps

```python
# Create fixture that can be used by steps
@given("the database has test data", target_fixture="test_data")
def create_test_data(db):
    """Create comprehensive test data."""
    user = User.objects.create_user(username='testuser')
    category = Category.objects.create(name='Test')
    articles = [
        Article.objects.create(
            title=f'Article {i}',
            author=user,
            category=category
        )
        for i in range(5)
    ]
    return {
        'user': user,
        'category': category,
        'articles': articles
    }


# Use in subsequent steps
@then("all test articles should exist")
def verify_articles(test_data):
    """Access fixture data in step."""
    assert len(test_data['articles']) == 5
    for article in test_data['articles']:
        article.refresh_from_db()
        assert article.title is not None
```
