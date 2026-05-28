# Complete Example: Blog Feature

Full working example of a blog post feature with all components.

## Feature File

**File:** `tests/acceptance/features/blog_posts.feature`

```gherkin
Feature: Blog Post Management
  As an author
  I want to create and manage blog posts
  So that I can share content with readers

  Background:
    Given I am logged in as an author
    And there is a category "Technology"

  Scenario: Create new draft post
    Given I am on the new post page
    When I enter title "Getting Started with Django"
    And I enter content "Django is a Python web framework..."
    And I select category "Technology"
    And I enter tags "django, python, tutorial"
    And I click save as draft
    Then I should see "Draft saved successfully"
    And the post should exist as a draft in the database

  Scenario: Publish a draft post
    Given I have a draft post "My Draft"
    And I am viewing the post edit page
    When I click publish
    And I confirm publication
    Then the post status should be "published"
    And the post should be visible at "/blog/my-draft/"
    And I should receive a publication confirmation email

  Scenario: Cannot publish without required fields
    Given I am on the new post page
    When I click publish without entering data
    Then I should see "Title is required"
    And I should see "Content is required"
    And no post should be created
```

## Models

```python
# blog/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify

User = get_user_model()


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class BlogPost(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    tags = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def is_published(self):
        return self.status == 'published'

    def __str__(self):
        return self.title
```

## Fixtures

**File:** `tests/acceptance/conftest.py`

```python
"""Blog acceptance test fixtures."""
import pytest
from django.contrib.auth import get_user_model
from blog.models import Category, BlogPost

User = get_user_model()


@pytest.fixture
def author_user(db):
    """Create an author user."""
    return User.objects.create_user(
        username='author',
        email='author@blog.com',
        password='AuthorPass123'
    )


@pytest.fixture
def tech_category(db):
    """Create Technology category."""
    return Category.objects.create(
        name='Technology',
        slug='technology'
    )


@pytest.fixture
def draft_post(db, author_user, tech_category):
    """Create a draft blog post."""
    return BlogPost.objects.create(
        title='My Draft',
        slug='my-draft',
        content='Draft content here',
        author=author_user,
        category=tech_category,
        status='draft'
    )
```

## Step Definitions

**File:** `tests/acceptance/step_defs/test_blog_posts.py`

```python
"""Blog post step definitions."""
import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from django.core.mail import outbox
from blog.models import BlogPost, Category

scenarios('../features/blog_posts.feature')


# Given steps
@given("I am logged in as an author", target_fixture="logged_in_author")
def login_as_author(browser, live_server, author_user):
    """Log in as author."""
    browser.visit(f'{live_server.url}/accounts/login/')
    browser.fill('username', 'author')
    browser.fill('password', 'AuthorPass123')
    browser.find_by_css('button[type="submit"]').first.click()
    return author_user


@given(parsers.parse('there is a category "{name}"'))
def category_exists(db, name):
    """Ensure category exists."""
    Category.objects.get_or_create(name=name, slug=name.lower())


@given("I am on the new post page")
def on_new_post_page(browser, live_server):
    """Navigate to new post page."""
    browser.visit(f'{live_server.url}/blog/new/')


@given(parsers.parse('I have a draft post "{title}"'), target_fixture="draft")
def have_draft_post(db, logged_in_author, tech_category, title):
    """Create draft post."""
    return BlogPost.objects.create(
        title=title,
        slug=title.lower().replace(' ', '-'),
        content='Draft content',
        author=logged_in_author,
        category=tech_category,
        status='draft'
    )


@given("I am viewing the post edit page")
def viewing_edit_page(browser, live_server, draft):
    """Navigate to post edit page."""
    browser.visit(f'{live_server.url}/blog/{draft.slug}/edit/')


# When steps
@when(parsers.parse('I enter title "{title}"'))
def enter_title(browser, title):
    """Fill in title field."""
    browser.fill('title', title)


@when(parsers.parse('I enter content "{content}"'))
def enter_content(browser, content):
    """Fill in content field."""
    browser.fill('content', content)


@when(parsers.parse('I select category "{category}"'))
def select_category(browser, category):
    """Select category from dropdown."""
    browser.select('category', category)


@when(parsers.parse('I enter tags "{tags}"'))
def enter_tags(browser, tags):
    """Fill in tags field."""
    browser.fill('tags', tags)


@when("I click save as draft")
def click_save_draft(browser):
    """Click save as draft button."""
    browser.find_by_css('button[name="save_draft"]').first.click()


@when("I click publish")
def click_publish(browser):
    """Click publish button."""
    browser.find_by_css('button[name="publish"]').first.click()


@when("I confirm publication")
def confirm_publication(browser):
    """Confirm in modal."""
    browser.find_by_css('button[name="confirm"]').first.click()


@when("I click publish without entering data")
def click_publish_empty(browser):
    """Submit form without data."""
    browser.find_by_css('button[name="publish"]').first.click()


# Then steps
@then(parsers.parse('I should see "{message}"'))
def should_see_message(browser, message):
    """Verify message displayed."""
    assert browser.is_text_present(message), f"Message '{message}' not found"


@then("the post should exist as a draft in the database")
def post_is_draft(db):
    """Verify draft post exists."""
    post = BlogPost.objects.get(title='Getting Started with Django')
    assert post.status == 'draft'
    assert not post.is_published


@then(parsers.parse('the post status should be "{status}"'))
def post_has_status(draft, status):
    """Verify post status."""
    draft.refresh_from_db()
    assert draft.status == status


@then(parsers.parse('the post should be visible at "{url}"'))
def post_visible_at_url(browser, live_server, url):
    """Verify post accessible at URL."""
    browser.visit(f'{live_server.url}{url}')
    # Should not get 404
    assert browser.status_code.is_success()


@then("I should receive a publication confirmation email")
def receive_confirmation_email():
    """Verify email sent."""
    assert len(outbox) > 0
    assert 'published' in outbox[-1].subject.lower()


@then("no post should be created")
def no_post_created(db):
    """Verify no posts exist."""
    assert BlogPost.objects.count() == 0
```

## Views (Simplified)

```python
# blog/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.utils import timezone
from .models import BlogPost, Category
from .forms import BlogPostForm


@login_required
def new_post(request):
    if request.method == 'POST':
        form = BlogPostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user

            if 'save_draft' in request.POST:
                post.status = 'draft'
                post.save()
                messages.success(request, 'Draft saved successfully')
            elif 'publish' in request.POST:
                post.status = 'published'
                post.published_at = timezone.now()
                post.save()

                # Send email
                send_mail(
                    f'Post published: {post.title}',
                    f'Your post has been published at /blog/{post.slug}/',
                    'noreply@blog.com',
                    [request.user.email]
                )
                messages.success(request, 'Post published successfully')

            return redirect('blog:edit', slug=post.slug)
    else:
        form = BlogPostForm()

    return render(request, 'blog/new_post.html', {'form': form})


@login_required
def edit_post(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, author=request.user)

    if request.method == 'POST':
        form = BlogPostForm(request.POST, instance=post)
        if form.is_valid():
            post = form.save(commit=False)

            if 'publish' in request.POST and post.status == 'draft':
                post.status = 'published'
                post.published_at = timezone.now()

                send_mail(
                    f'Post published: {post.title}',
                    f'Your post has been published at /blog/{post.slug}/',
                    'noreply@blog.com',
                    [request.user.email]
                )

            post.save()
            messages.success(request, 'Post updated')
            return redirect('blog:edit', slug=post.slug)
    else:
        form = BlogPostForm(instance=post)

    return render(request, 'blog/edit_post.html', {
        'form': form,
        'post': post
    })


def post_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, status='published')
    return render(request, 'blog/post_detail.html', {'post': post})
```

## Running the Tests

```bash
# Run blog tests
pytest tests/acceptance/step_defs/test_blog_posts.py -v

# Run specific scenario
pytest -k "Create new draft post"

# Run with output
pytest tests/acceptance/step_defs/test_blog_posts.py -v -s
```

## Output

```
tests/acceptance/step_defs/test_blog_posts.py::test_create_new_draft_post PASSED
tests/acceptance/step_defs/test_blog_posts.py::test_publish_a_draft_post PASSED
tests/acceptance/step_defs/test_blog_posts.py::test_cannot_publish_without_required_fields PASSED
```

---

# Complete Example: E-commerce Checkout

## Feature File

```gherkin
Feature: Shopping Cart Checkout
  As a customer
  I want to complete purchases
  So that I can receive products

  Background:
    Given there are products available:
      | name      | price | stock |
      | Widget A  | 29.99 | 10    |
      | Widget B  | 19.99 | 5     |

  Scenario: Complete purchase with valid payment
    Given I am on the products page
    When I add "Widget A" to cart
    And I add "Widget B" to cart
    Then my cart should contain 2 items
    And the cart total should be "$49.98"

    When I click checkout
    And I fill in shipping address:
      | field   | value         |
      | name    | John Doe      |
      | address | 123 Main St   |
      | city    | Portland      |
      | state   | OR            |
      | zip     | 97201         |
    And I fill in payment:
      | field  | value            |
      | card   | 4242424242424242 |
      | expiry | 12/25            |
      | cvv    | 123              |
    And I click place order
    Then I should see "Order confirmed"
    And I should receive an order confirmation email
    And product stock should be decremented

  Scenario: Insufficient stock
    Given I have 6 "Widget B" in my cart
    When I try to checkout
    Then I should see "Insufficient stock"
    And my order should not be processed
```

## Step Definitions

```python
"""E-commerce checkout steps."""
from pytest_bdd import scenarios, given, when, then, parsers
from decimal import Decimal
from shop.models import Product, Order

scenarios('../features/checkout.feature')


@given("there are products available:")
def create_products(db, datatable):
    """Create products from table."""
    for row in datatable:
        Product.objects.create(
            name=row['name'],
            price=Decimal(row['price']),
            stock=int(row['stock'])
        )


@when(parsers.parse('I add "{product_name}" to cart'))
def add_to_cart(browser, product_name):
    """Add product to cart."""
    browser.find_link_by_text(product_name).first.click()
    browser.find_by_css('button[name="add_to_cart"]').first.click()


@then(parsers.parse('my cart should contain {count:d} items'))
def verify_cart_count(browser, count):
    """Verify cart item count."""
    cart_count = browser.find_by_css('.cart-count').first.text
    assert int(cart_count) == count


@then(parsers.parse('the cart total should be "{total}"'))
def verify_cart_total(browser, total):
    """Verify cart total."""
    displayed_total = browser.find_by_css('.cart-total').first.text
    assert total in displayed_total


@when("I click checkout")
def click_checkout(browser):
    """Proceed to checkout."""
    browser.find_link_by_text('Checkout').first.click()


@when("I fill in shipping address:")
def fill_shipping(browser, datatable):
    """Fill shipping form."""
    for row in datatable:
        browser.fill(f'shipping_{row["field"]}', row['value'])


@when("I fill in payment:")
def fill_payment(browser, datatable):
    """Fill payment form."""
    for row in datatable:
        browser.fill(f'payment_{row["field"]}', row['value'])


@when("I click place order")
def place_order(browser):
    """Submit order."""
    browser.find_by_css('button[name="place_order"]').first.click()


@then("I should receive an order confirmation email")
def verify_order_email():
    """Check confirmation email."""
    from django.core.mail import outbox
    assert len(outbox) > 0
    assert 'Order confirmed' in outbox[-1].subject


@then("product stock should be decremented")
def verify_stock_decremented(db):
    """Verify stock updated."""
    widget_a = Product.objects.get(name='Widget A')
    widget_b = Product.objects.get(name='Widget B')
    assert widget_a.stock == 9  # Was 10, now 9
    assert widget_b.stock == 4  # Was 5, now 4
```

This example demonstrates:
- Table-driven test data
- Multi-step workflows
- Form filling
- Email verification
- Database state verification
- Decimal handling for prices
