# Custom Endpoint Notes

## Authentication

- `POST /api/v1/auth/register`: creates an inactive account, profile, and activation token.
- `GET /api/v1/auth/activate/{token}`: activates an account while the token is still valid.
- `POST /api/v1/auth/resend-activation`: issues a new activation token for inactive users.
- `POST /api/v1/auth/login`: returns access and refresh JWT tokens.
- `POST /api/v1/auth/refresh`: validates the persisted refresh token and returns a new access token.
- `POST /api/v1/auth/logout`: revokes the refresh token.
- `POST /api/v1/auth/change-password`: verifies the old password and invalidates active refresh tokens.
- `POST /api/v1/auth/forgot-password`: creates a password reset token and sends an email for active users.
- `POST /api/v1/auth/reset-password/{token}`: resets the password without the old password when the reset token is valid.

## Movies and Interactions

- `GET /api/v1/movies`: supports pagination, search, genre filtering, IMDb filtering, and sorting.
- `POST /api/v1/movies/{movie_id}/favorite`: adds a movie to the authenticated user's favorites.
- `POST /api/v1/movies/{movie_id}/reaction`: stores a like or dislike for the authenticated user.
- `POST /api/v1/movies/{movie_id}/rating`: stores a 1-10 rating for the authenticated user.
- `POST /api/v1/movies/{movie_id}/comments`: creates a top-level movie comment.
- `POST /api/v1/comments/{comment_id}/reply`: creates a reply and notifies the original comment author.
- `POST /api/v1/comments/{comment_id}/like`: likes a comment and notifies the comment author.

## Commerce

- `POST /api/v1/cart/items/{movie_id}`: adds an available, not-yet-purchased movie to the cart.
- `POST /api/v1/orders`: creates a pending order from valid cart items and removes those items from the cart.
- `POST /api/v1/orders/{order_id}/pay`: revalidates prices, creates payment records, and finalizes immediately in `fake` payment mode.
- `POST /api/v1/payments/webhook/stripe`: finalizes pending Stripe-backed payments from webhook events.
- `POST /api/v1/payments/{payment_id}/refund`: refunds a successful payment and removes purchased access for that payment.

## Admin

- `GET /api/v1/admin/carts`: reviews user carts.
- `GET /api/v1/admin/orders`: reviews orders with optional user/status filters.
- `GET /api/v1/admin/payments`: reviews payments with optional user/status filters.
- `PATCH /api/v1/admin/users/{user_id}/group`: updates the user's role.
- `POST /api/v1/admin/users/{user_id}/activate`: manually activates a user account.
