#!/bin/bash
if [ $# -eq 0 ]; then
    echo "Please provide the username under which the program will be installed"
    exit 1
fi
priv_ok=false
if [[ $EUID -eq 1 ]]; then
    priv_ok=true
else
    sudo -k # make sure to ask for password on next sudo
    if sudo true; then
        priv_ok=true
    else
        priv_ok=false
    fi
fi
if "$priv_ok"; then
    # Password will not be asked again due to caching.
    echo -n "Making installation directory..."
    if sudo mkdir -p /etc/wpable > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
       exit 1
    fi
    echo -n "Changing ownership of installation directory..."
    if sudo chown $1 /etc/wpable > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
    echo -n "Changing to installation directory..."
    if cd /etc/wpable > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
    echo -n "Getting installation files..."
    if git clone git@github.com:samedayrules/wpable_server.git temp > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
    echo -n "Copying files to final destination..."
    if mv temp/* . > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
    echo -n "Removing temporary files..."
    if sudo rm -R temp > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
    echo -n "Making python virtual environment..."
    if python -m venv venv > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
    echo -n "Activating virtual environment..."
    if source venv/bin/activate > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
    echo -n "Installing python packages..."
    if pip install -r requirements.txt > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
    echo -n "Changing source files to target supplied username..."
    if sed -i "s/linux/$1/g" service-auth.pkla wpable.conf > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi  
    echo -n "Configuring supervisor to run program automatically..."
    if sudo cp wpable.conf /etc/supervisor/conf.d/wpable.conf > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
    echo -n "Setting wpa_supplicant file permissions..."
    if sudo chown $1 /etc/wpa_supplicant/wpa_supplicant.conf > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
    echo -n "Creating program log file..."
    if sudo touch /var/log/wpable.log > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
    echo -n "Changing permission on program log file..."
    if sudo chown $1 /var/log/wpable.log > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
    echo -n "Allow program to re-start system services..."
    if sudo cp /etc/wpable/service-auth.pkla /etc/polkit-1/localauthority/50-local.d > /dev/null 2>&1 ; then
        echo "success"
    else
        echo "failed"
        exit 1
    fi
else
    echo "Insufficient user privelege to continue"
fi
