# Use the official Nginx base image
FROM nginx:alpine

# Copy the HTML file to the Nginx default public directory
COPY index.html /usr/share/nginx/html/

# Expose port 80 to allow access to the Nginx server
EXPOSE 80

# Start the Nginx server when the container runs
CMD ["nginx", "-g", "daemon off;"]
